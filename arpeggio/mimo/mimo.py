"""Uplink MU-MIMO detection with Ising solvers (DESIGN.md). Batched on one GPU with PyTorch.

System: y = H x + n, H (Nr x Nt) complex, i.i.d. CN(0, 1) entries (or receive-correlated, exponential rho), x drawn
from unit-energy Gray QAM (QPSK, 16-QAM), n ~ CN(0, N0 I). SNR = Nt * Es / N0 (received SNR per antenna, Es = 1).

Ising mapping (Kim, Jamieson, Singh, arXiv:2105.10535, Sec. II and Eq. 7, 9): real-valued lift, per real dimension the
PAM level is l = T s (QPSK: l = s; 16-QAM: l = 2 s1 + s2), so ||y - H x||^2 = -h^T s - s^T J s + const with
h = 2 T^T H^T y and J = -offdiag(T^T H^T H T); coefficients scaled into [-1, 1] by their maximum magnitude; the RI-MIMO
regularisation r ||s - s_P||^2 (r = 0.15, s_P the spins of the hard MMSE estimate) gives h_reg = h + 2 r s_P.
Final decision: the candidate with the lowest ||y - H x||^2 among the solver's candidates and the MMSE estimate.
"""
import math

import numpy as np
import torch

# ---------------------------------------------------------------- constellations (Gray, per real dimension)
# PAM levels in integer units l and the per-dimension scale a: x_re = a * l. Bits per real dimension: 1 (QPSK) or 2.
PAM = {4: dict(levels=[-1, 1], a=1 / math.sqrt(2), bits=1),
       16: dict(levels=[-3, -1, 1, 3], a=1 / math.sqrt(10), bits=2)}
# Gray bits of each level (MSB first): QPSK -1 -> 0, +1 -> 1; 16-QAM -3 00, -1 01, +1 11, +3 10.
GRAY = {4: {-1: (0,), 1: (1,)}, 16: {-3: (0, 0), -1: (0, 1), 1: (1, 1), 3: (1, 0)}}


def level_bits(M):
    lv = PAM[M]['levels']
    return torch.tensor([GRAY[M][l] for l in lv], dtype=torch.int8)        # (L, bits)


def levels_to_spins(l, M):
    """Integer PAM levels -> Princeton spins (natural binary: l = 2 s1 + s2 for 16-QAM). l: (..., D) -> (..., D * rb)."""
    if M == 4:
        return l.clone()
    s1 = torch.where(l > 0, 1.0, -1.0)
    s2 = torch.where((l == 3) | (l == -1), 1.0, -1.0)
    return torch.cat([s1, s2], dim=-1)                                     # spin order: all MSBs, then all LSBs (T = [2I, I])


def spins_to_levels(s, M, D):
    if M == 4:
        return s
    return 2 * s[..., :D] + s[..., D:]


def levels_to_bits(l, M):
    """(..., D) integer levels -> (..., D * bits) Gray bits (int8), per dimension MSB first."""
    if M == 4:
        return (l > 0).to(torch.int8)
    b1 = (l > 0).to(torch.int8)
    b2 = (l.abs() == 1).to(torch.int8)
    return torch.stack([b1, b2], dim=-1).flatten(-2)


# ---------------------------------------------------------------- channels and transmission
def complex_to_real(Hc):
    """(B, Nr, Nt) complex -> (B, 2Nr, 2Nt) real lift [[Re, -Im], [Im, Re]]."""
    Hr, Hi = Hc.real, Hc.imag
    return torch.cat([torch.cat([Hr, -Hi], -1), torch.cat([Hi, Hr], -1)], -2)


def make_batch(B, Nt, Nr, M, snr_db, gen, rho=0.0, device='cuda', levels=None):
    """One batch of channel uses: returns dict with real-valued H (scaled by a), y, true levels, N0.
    levels: optional (B, 2Nt) transmitted integer levels (coded runs); else uniform random."""
    a = PAM[M]['a']
    lv = torch.tensor(PAM[M]['levels'], device=device, dtype=torch.float32)
    if levels is None:
        idx = torch.randint(0, len(lv), (B, 2 * Nt), generator=gen, device=device)
        l = lv[idx]                                                        # (B, 2Nt): real parts then imaginary parts
    else:
        l = levels.to(device)
    Hc = torch.complex(torch.randn(B, Nr, Nt, generator=gen, device=device),
                       torch.randn(B, Nr, Nt, generator=gen, device=device)) / math.sqrt(2)
    if rho > 0:                                                            # receive correlation R_ij = rho^|i-j| (BS ULA)
        i = torch.arange(Nr, device=device, dtype=torch.float32)
        Rm = rho ** (i[:, None] - i[None, :]).abs()
        Lc = torch.linalg.cholesky(Rm).to(torch.complex64)
        Hc = Lc @ Hc
    H = complex_to_real(Hc) * a                                            # y = (a H~) l + n
    N0 = Nt * 1.0 / (10 ** (snr_db / 10))                                  # Es = 1 per complex symbol
    n = torch.randn(B, 2 * Nr, generator=gen, device=device) * math.sqrt(N0 / 2)
    y = torch.einsum('bij,bj->bi', H, l) + n
    return dict(H=H, y=y, l=l, N0=N0, M=M, Nt=Nt, Nr=Nr)


# ---------------------------------------------------------------- MMSE (hard and soft)
def quantize_levels(z, M):
    lv = torch.tensor(PAM[M]['levels'], device=z.device, dtype=z.dtype)
    return lv[(z[..., None] - lv).abs().argmin(-1)]


def mmse_hard(b, z, Ainv):
    """Hard MMSE decision on the bias-corrected output z / mu (mu = diag(W H)), the usual unbiased MMSE detector."""
    G = b['H'].transpose(1, 2) @ b['H']
    mu = torch.diagonal(Ainv @ G, dim1=-2, dim2=-1)
    return quantize_levels(z / mu, b['M'])


def mmse(b):
    """Real-valued LMMSE: x_hat = (H^T H + (N0/2)/(a^2... ) handled in level units: W = (H^T H + s2/sl2 I)^-1 H^T,
    with noise variance N0/2 per real dimension and level variance E[l^2] per real dimension."""
    H, y, M = b['H'], b['y'], b['M']
    lv = torch.tensor(PAM[M]['levels'], dtype=torch.float32)
    el2 = float((lv ** 2).mean())
    G = H.transpose(1, 2) @ H
    D = G.shape[-1]
    A = G + (b['N0'] / 2) / el2 * torch.eye(D, device=H.device)
    Ainv = torch.linalg.inv(A)
    z = torch.einsum('bij,bj->bi', Ainv @ H.transpose(1, 2), y)
    return z, Ainv, el2


def mmse_soft_llr(b, z, Ainv, el2):
    """Max-log LLRs per bit from the MMSE output with the standard unbiased Gaussian approximation.
    Per real dimension k: W H has diagonal mu_k; z_k = mu_k l_k + e_k, Var(e_k) = el2 mu_k (1 - mu_k).
    LLR(b) = log P(b=1)/P(b=0) (max-log over levels)."""
    H, M = b['H'], b['M']
    G = H.transpose(1, 2) @ H
    mu = torch.diagonal(Ainv @ G, dim1=-2, dim2=-1)                        # (B, D)
    var = el2 * mu * (1 - mu)
    lv = torch.tensor(PAM[M]['levels'], device=H.device, dtype=torch.float32)
    d2 = (z[..., None] - mu[..., None] * lv) ** 2 / var[..., None].clamp_min(1e-12)   # (B, D, L)
    bits = level_bits(M).to(H.device)                                      # (L, nb)
    llr = []
    for k in range(bits.shape[1]):
        m1 = torch.where(bits[:, k].bool(), d2, torch.full_like(d2, float('inf'))).amin(-1)
        m0 = torch.where(~bits[:, k].bool(), d2, torch.full_like(d2, float('inf'))).amin(-1)
        llr.append((m0 - m1) / 2)                                          # log-likelihood ratio, max-log
    return torch.stack(llr, -1).flatten(-2)                                # (B, D * nb), per dimension MSB first


# ---------------------------------------------------------------- Ising mapping (Princeton)
def ising(b, z_mmse, r=0.15):
    """Returns h_reg, J (scaled), h0 (scaled, unregularised), s_P, T-matrix and the scale."""
    H, y, M = b['H'], b['y'], b['M']
    D = H.shape[-1]
    if M == 4:
        T = torch.eye(D, device=H.device)
    else:
        I = torch.eye(D, device=H.device)
        T = torch.cat([2 * I, I], dim=1)                                   # l = T s, s = [s_MSB; s_LSB]
    HT = H @ T
    h = 2 * torch.einsum('bij,bi->bj', HT, y)
    Q = HT.transpose(1, 2) @ HT
    J = -(Q - torch.diag_embed(torch.diagonal(Q, dim1=-2, dim2=-1)))
    scale = torch.maximum(h.abs().amax(-1), J.abs().flatten(1).amax(-1)).clamp_min(1e-12)   # (B,)
    h0 = h / scale[:, None]
    J = J / scale[:, None, None]
    sP = levels_to_spins(quantize_levels(z_mmse, M), M)
    return dict(h=h0 + 2 * r * sP, h0=h0, J=J, sP=sP, T=T, scale=scale, r=r)


def ising_delta(b, z_mmse, K=1):
    """Princeton's delta Ising formulation (dDI; Singh et al., IEEE TWC 2024, arXiv:2304.12830 Sec. III): around the
    quantised MMSE estimate x_q, each real dimension's correction d = sum_k s_k over 2K spins (degenerate encoding
    T = 1_(1x2K) (x) I), so d is in {-2K, ..., 2K} in steps of 2 and every step is one spin flip (no barrier);
    ||ybar - H T s||^2 with ybar = y - H x_q gives h = 2 T^T H^T ybar, J = -offdiag(T^T H^T H T), scaled into [-1, 1];
    no RI penalty (the formulation is local). Candidate levels: x_q + T s clipped to the constellation (spins_to_levels_delta)."""
    H, y, M = b['H'], b['y'], b['M']
    D = H.shape[-1]
    xq = mmse_hard(b, z_mmse, None) if False else None
    I_ = torch.eye(D, device=H.device)
    T = torch.cat([I_] * (2 * K), dim=1)                                   # (D, 2K D)
    xq = quantize_levels(z_mmse / _mu(b, z_mmse), M)
    yb = y - torch.einsum('bij,bj->bi', H, xq)
    HT = H @ T
    h = 2 * torch.einsum('bij,bi->bj', HT, yb)
    Q = HT.transpose(1, 2) @ HT
    J = -(Q - torch.diag_embed(torch.diagonal(Q, dim1=-2, dim2=-1)))
    scale = torch.maximum(h.abs().amax(-1), J.abs().flatten(1).amax(-1)).clamp_min(1e-12)
    h0 = h / scale[:, None]
    J = J / scale[:, None, None]
    sP = torch.cat([torch.ones(h0.shape[0], D, device=H.device), -torch.ones(h0.shape[0], D, device=H.device)] * K, dim=1)  # d = 0
    return dict(h=h0, h0=h0, J=J, sP=sP, T=T, scale=scale, r=0.0, xq=xq, K=K, delta=True)


def _mu(b, z):
    H = b['H']
    lv = torch.tensor(PAM[b['M']]['levels'], dtype=torch.float32)
    el2 = float((lv ** 2).mean())
    G = H.transpose(1, 2) @ H
    A = G + (b['N0'] / 2) / el2 * torch.eye(G.shape[-1], device=H.device)
    return torch.diagonal(torch.linalg.solve(A, G), dim1=-2, dim2=-1)


def spins_to_levels_delta(S, I, M):
    """Delta formulation: levels x_q + T s, clipped to the constellation's range (S: (B, R, 2K D))."""
    D = I['xq'].shape[-1]
    d = S.reshape(*S.shape[:-1], 2 * I['K'], D).sum(-2)
    lv = PAM[M]['levels']
    return (I['xq'][:, None, :] + d).clamp(lv[0], lv[-1])


def energy0(s, h0, J):
    """Unregularised scaled Ising energy -h0.s - s^T J s for s (B, R, N)."""
    return -(s * h0[:, None, :]).sum(-1) - (s * torch.einsum('bij,brj->bri', J, s)).sum(-1)


# ---------------------------------------------------------------- solvers
def geom(t0, t1, S, device):
    k = torch.arange(S, device=device, dtype=torch.float64)
    return (t0 * (t1 / t0) ** (k / max(1, S - 1))).to(torch.float32)


@torch.no_grad()
def anechoic(I, R, S, t0, t1, q, kappa=0.0, lam=0.0, ramp=True, gen=None, track='best', warm=False, phases=1):
    """Onsager-corrected SCA (fpga27 Algorithm 1 / Eq. 3-4), batched over instances and R anneals per instance.
    Field u = h + 2 J s (the energy change of flipping i is 2 s_i u_i). Decision z = s (u - c s') + q with
    c = kappa T_{t-1} rho_t (Onsager-kT) or lam rho_t n_lin(t-1) / (2 T_{t-1}) (Onsager-online); flip if z < r,
    r uniform in [-2T, 2T). Random start. Returns the best-energy state of each anneal (track='best') or the final state."""
    h, J = I['h'], I['J']
    B, N = h.shape
    dev = h.device
    T = geom(t0, t1, S, dev)
    rho = torch.ones(S, device=dev)
    if ramp:
        t = torch.arange(S, device=dev, dtype=torch.float32)
        rho = torch.where(t >= 0.7 * S, (S - 1 - t) / max(1.0, S - 1 - 0.7 * S), torch.ones_like(t))
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    if warm:                                                               # our variant: start at the MMSE spins
        s = I['sP'][:, None, :].expand(B, R, N).clone()
    sprev = s.clone()
    nlin_prev = torch.zeros(B, R, 1, device=dev)
    best_s, best_e = s.clone(), torch.full((B, R), float('inf'), device=dev)
    for k in range(S):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        if k == 0:
            c = torch.zeros(B, R, 1, device=dev)
        elif lam > 0:
            c = lam * rho[k] * nlin_prev / (2 * T[k - 1])
        else:
            c = torch.full((B, R, 1), float(kappa) * float(T[k - 1]) * float(rho[k]), device=dev)
        z = s * (u - c * sprev) + q
        rr = (torch.rand(B, R, N, generator=gen, device=dev) - 0.5) * 4 * T[k]
        nlin_prev = ((z > -2 * T[k]) & (z < 2 * T[k])).sum(-1, keepdim=True).float()
        flip = z < rr
        if phases > 1:                                                     # our variant: the P spin copies of the delta
            P_ = phases                                                    # encoding update in turn (copy k mod P at step k)
            idx = torch.arange(N, device=dev) // (N // P_)
            flip = flip & (idx == (k % P_))
        sprev = s
        s = torch.where(flip, -s, s)
        if track == 'best':
            e = energy0(s, I['h0'], J)
            better = e < best_e
            best_e = torch.where(better, e, best_e)
            best_s = torch.where(better[..., None], s, best_s)
    if track == 'best':
        return best_s
    return s


@torch.no_grad()
def cim(I, R, steps=128, dt=0.01, C=math.sqrt(10), As=10.0, gen=None, track='best', pump='step'):
    """Princeton's RI-MIMO CIM model (arXiv:2105.10535 Eq. 8, after Haribara et al.): c-number SDEs
    dc = [(-1 + p - c^2 - q^2) c + C sum_j Jt_ij c_j] dt + (1/As) sqrt(c^2 + q^2 + 1/2) dW1,
    dq = (-1 - p - c^2 - q^2) q dt + (1/As) sqrt(c^2 + q^2 + 1/2) dW2, p_k = 2 tanh(2 k / N) at step k,
    Euler-Maruyama with dt = 0.01, 128 steps, C = sqrt(10); the field enters through an auxiliary spin (Jt_ia = h_i / 2),
    spins s = sign(c_i) sign(c_a), one measurement per step (Nm = 128). As and the start c = q = 0 are not published
    (ledger rulings). pump='step': p_k = 2 tanh(2 k / N) with k the step index (p sweeps 0 -> 2 as the paper says);
    pump='time': p = 2 tanh(2 t / N) with t = k dt the normalised time."""
    h, J = I['h'], I['J']
    B, N = h.shape
    dev = h.device
    Jt = torch.zeros(B, N + 1, N + 1, device=dev)
    Jt[:, :N, :N] = J
    Jt[:, :N, N] = h / 2
    Jt[:, N, :N] = h / 2
    c = torch.zeros(B, R, N + 1, device=dev)
    qd = torch.zeros(B, R, N + 1, device=dev)
    best_s, best_e = None, torch.full((B, R), float('inf'), device=dev)
    sq = math.sqrt(dt)
    for k in range(1, steps + 1):
        p = 2 * math.tanh(2 * (k if pump == 'step' else k * dt) / N)
        a2 = c * c + qd * qd
        amp = torch.sqrt(a2 + 0.5) / As * sq
        cJ = torch.einsum('bij,brj->bri', Jt, c)
        c_new = c + ((-1 + p - a2) * c + C * cJ) * dt + amp * torch.randn(B, R, N + 1, generator=gen, device=dev)
        qd = qd + ((-1 - p - a2) * qd) * dt + amp * torch.randn(B, R, N + 1, generator=gen, device=dev)
        c = c_new
        s = torch.where(c[..., :N] * c[..., N:N + 1] >= 0, 1.0, -1.0)
        if track == 'best':
            e = energy0(s, I['h0'], J)
            better = e < best_e
            best_e = torch.where(better, e, best_e)
            best_s = s if best_s is None else torch.where(better[..., None], s, best_s)
    if track == 'best':
        return best_s
    return torch.where(c[..., :N] * c[..., N:N + 1] >= 0, 1.0, -1.0)


@torch.no_grad()
def ahc(I, R, steps=512, dt=0.005, p=0.98, a=2.0, beta=1.0, eps_max=1000.0, x0_var=0.001, gen=None):
    """CIM with amplitude-heterogeneity correction (Singh et al., IEEE TWC 2024, arXiv:2304.12830 Eqs. 9-10, after
    Leleu et al.): dx_i/dt = (p - 1) x_i - x_i^3 + eps e_i sum_j Jt_ij x_j, de_i/dt = -beta (x_i^2 - a) e_i,
    eps = gamma t ramped from 0 to 1000 (gamma = 1000 / (512 dt)), p = 0.98, a = 2, beta = 1, RK4 with 512 steps of
    dt = 0.005, x ~ N(0, 0.001) and e ~ |N(0, 0.001)| (variance 0.001; ledger), field via the auxiliary spin,
    spins s = sign(x_i) sign(x_a), every integration step's state a candidate (best by energy kept per anneal)."""
    h, J = I['h'], I['J']
    B, N = h.shape
    dev = h.device
    Jt = torch.zeros(B, N + 1, N + 1, device=dev)
    Jt[:, :N, :N] = J
    Jt[:, :N, N] = h / 2
    Jt[:, N, :N] = h / 2
    sd = math.sqrt(x0_var)
    x = torch.randn(B, R, N + 1, generator=gen, device=dev) * sd
    e = (torch.randn(B, R, N + 1, generator=gen, device=dev) * sd).abs()
    gamma = eps_max / (steps * dt)

    def f(t, x, e):
        jx = torch.einsum('bij,brj->bri', Jt, x)
        return (p - 1) * x - x ** 3 + gamma * t * e * jx, -beta * (x * x - a) * e

    best_s, best_e = None, torch.full((B, R), float('inf'), device=dev)
    for k in range(steps):
        t = k * dt
        k1x, k1e = f(t, x, e)
        k2x, k2e = f(t + dt / 2, x + dt / 2 * k1x, e + dt / 2 * k1e)
        k3x, k3e = f(t + dt / 2, x + dt / 2 * k2x, e + dt / 2 * k2e)
        k4x, k4e = f(t + dt, x + dt * k3x, e + dt * k3e)
        x = x + dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
        e = e + dt / 6 * (k1e + 2 * k2e + 2 * k3e + k4e)
        s = torch.where(x[..., :N] * x[..., N:N + 1] >= 0, 1.0, -1.0)
        en = energy0(s, I['h0'], J)
        better = en < best_e
        best_e = torch.where(better, en, best_e)
        best_s = s if best_s is None else torch.where(better[..., None], s, best_s)
    return best_s


@torch.no_grad()
def anechoic_soft(I, b, R, S, tpost_mult, q, t_hot=None, hot_frac=0.0, gen=None, t_abs=None, reg=False, warm=False):
    """Anechoic's SCA rule used as a sampler of the detection posterior p(x | y) ~ exp(-||y - Hx||^2 / N0).
    SCA at temperature T approximates Glauber dynamics at 2T in units of the flip energy 2 s u, so the posterior
    temperature is T_post = N0 / (2 scale) per instance (scale: the Ising coefficient scale); the field is the
    unregularised h0 (the posterior has no MMSE penalty). The chain runs at
    T = tpost_mult * T_post (an optional hot start at t_hot for the first hot_frac of the steps, geometric to T),
    and for every bit tracks the smallest ||y - Hx||^2 seen with that bit 0 and with it 1, over all visited states of all
    R anneals (max-log over the trajectory). Returns best levels (B, D), m0, m1 (B, D*nb) in ||y - Hx||^2 units.
    t_abs: run at this fixed temperature (scaled units) instead; max-log LLRs need only a rich visited set, and the
    LLR itself uses the true N0, so the exploration temperature is free (at T_post the synchronous rule with q = 0
    oscillates: every misaligned spin flips at once). reg: explore with the RI-MIMO regularised field h instead of h0;
    warm: start the chains at the MMSE spins instead of random ones."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    M = b['M']
    D = b['H'].shape[-1]
    scale = I['scale']
    Tp = (b['N0'] / (2 * scale) * tpost_mult)[:, None, None]               # (B, 1, 1)
    if t_abs is not None:                                                  # a fixed temperature in scaled units
        Tp = torch.full((B, 1, 1), float(t_abs), device=dev)
    if t_hot is not None and hot_frac > 0:
        nh = max(1, int(hot_frac * S))
    else:
        nh = 0
    const = None
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    if warm:                                                               # start every chain at the MMSE spins
        s = I['sP'][:, None, :].expand(B, R, N).clone()
    hf = h if reg else h0                                                  # exploration field (the LLRs use exact distances)
    nbits = D * PAM[M]['bits']
    inf = float('inf')
    m0 = torch.full((B, nbits), inf, device=dev)
    m1 = torch.full((B, nbits), inf, device=dev)
    best_d = torch.full((B,), inf, device=dev)
    best_l = torch.zeros(B, D, device=dev)
    # the constant of ||y - Hx||^2 = scale * E0(s) + c: from one reference state (the MMSE spins)
    sP = I['sP'][:, None, :]
    c0 = dist(b, spins_to_levels(sP, M, D)) - scale[:, None] * energy0(sP, h0, J)          # (B, 1)
    for k in range(S):
        if k < nh:
            T = (t_hot * (Tp / t_hot) ** (k / max(1, nh - 1))) if nh > 1 else Tp
        else:
            T = Tp
        u = hf[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        z = s * u + q
        rr = (torch.rand(B, R, N, generator=gen, device=dev) - 0.5) * 4 * T
        s = torch.where(z < rr, -s, s)
        d = scale[:, None] * energy0(s, h0, J) + c0                         # (B, R): ||y - Hx||^2 of each chain
        l = spins_to_levels(s, M, D)
        bits = levels_to_bits(l, M).bool()                                  # (B, R, nbits)
        dd = d[..., None].expand_as(bits)
        m1 = torch.minimum(m1, torch.where(bits, dd, inf).amin(1))
        m0 = torch.minimum(m0, torch.where(~bits, dd, inf).amin(1))
        dm, im = d.min(1)
        better = dm < best_d
        best_d = torch.where(better, dm, best_d)
        best_l = torch.where(better[:, None], l[torch.arange(B, device=dev), im], best_l)
    return best_l, best_d, m0, m1


def trajectory_llr(b, best_l, best_d, m0, m1, mmse_levels, clip=50.0):
    """LLRs from the trajectory minima plus the MMSE estimate and the single-bit-flip neighbours of the best state."""
    M, N0 = b['M'], b['N0']
    allc = torch.stack([best_l, mmse_levels], 1)
    d = dist(b, allc)
    l_hat = allc[torch.arange(allc.shape[0], device=allc.device), d.argmin(1)]
    # fold the list (best, MMSE, bit-flip neighbours of l_hat) into the per-bit minima
    llr_list = list_llr(b, allc, d, l_hat, clip=float('inf'))               # uses its own minima; recompute below
    bits = levels_to_bits(allc, M).bool()
    inf = float('inf')
    m1 = torch.minimum(m1, torch.where(bits, d[..., None], inf).amin(1))
    m0 = torch.minimum(m0, torch.where(~bits, d[..., None], inf).amin(1))
    llr = (m0 - m1) / N0
    # bits without a counter-hypothesis in the trajectory take the list LLR (bit-flip neighbours)
    llr = torch.where(torch.isfinite(llr), llr, llr_list)
    return l_hat, llr.clamp(-clip, clip)


# ---------------------------------------------------------------- decisions, errors, soft output
def candidates_to_levels(S, M, D):
    return spins_to_levels(S, M, D)


def dist(b, l):
    """||y - H l||^2 for candidate levels l (B, K, D)."""
    return ((b['y'][:, None, :] - torch.einsum('bij,bkj->bki', b['H'], l)) ** 2).sum(-1)


def select(b, cand_levels, mmse_levels):
    """Lowest ||y - H x||^2 among candidates (B, K, D) and the MMSE estimate."""
    allc = torch.cat([cand_levels, mmse_levels[:, None, :]], 1)
    d = dist(b, allc)
    return allc[torch.arange(allc.shape[0], device=allc.device), d.argmin(1)], allc, d


def bit_errors(b, l_hat):
    bt = levels_to_bits(b['l'], b['M'])
    bh = levels_to_bits(l_hat, b['M'])
    return int((bt != bh).sum()), bt.numel()


def list_llr(b, allc, d, best, clip=50.0):
    """Max-log LLRs from a candidate list: the list (allc, d) plus the single-bit-flip neighbours of the best candidate.
    LLR(b_k) = (min_{x: b_k = 0} d(x) - min_{x: b_k = 1} d(x)) / N0 (natural log units), clipped to +-clip."""
    M, N0 = b['M'], b['N0']
    B, D = best.shape
    nb = PAM[M]['bits']
    lv = torch.tensor(PAM[M]['levels'], device=best.device, dtype=torch.float32)
    bits_best = levels_to_bits(best, M)                                    # (B, D*nb)
    # neighbours: flip one Gray bit of one dimension -> the level with that bit flipped
    nbr = []
    gray = level_bits(M).to(best.device)                                   # (L, nb)
    for dim in range(D):
        for k in range(nb):
            cur = best[:, dim]
            idx = (cur[:, None] == lv).float().argmax(1)
            want = gray[idx].clone()
            want[:, k] = 1 - want[:, k]
            new_idx = (gray[None, :, :] == want[:, None, :]).all(-1).float().argmax(1)
            x = best.clone()
            x[:, dim] = lv[new_idx]
            nbr.append(x)
    nbr = torch.stack(nbr, 1)                                              # (B, D*nb, D)
    allc2 = torch.cat([allc, nbr], 1)
    d2 = torch.cat([d, dist(b, nbr)], 1)
    bits = levels_to_bits(allc2, M)                                        # (B, K, D*nb)
    inf = torch.tensor(float('inf'), device=best.device)
    m1 = torch.where(bits.bool(), d2[..., None], inf).amin(1)
    m0 = torch.where(~bits.bool(), d2[..., None], inf).amin(1)
    return ((m0 - m1) / N0).clamp(-clip, clip)


# ---------------------------------------------------------------- milestone B: MMSE-SIC and MDI-MIMO
@torch.no_grad()
def mmse_sic(b, per='real'):
    """Ordered MMSE-SIC (Liu, IEEE TWC 2009, "optimal ordering": at each stage detect the stream with the smallest
    MMSE error variance, quantise its bias-corrected estimate, cancel it, repeat). per='real': the 2 Nt real streams
    of the real-valued model are ordered individually; per='complex': each user (both real dimensions) at once.
    Returns integer levels (B, D)."""
    H, y, M = b['H'], b['y'].clone(), b['M']
    B, _, D = H.shape
    Nt = D // 2
    dev = H.device
    lv = torch.tensor(PAM[M]['levels'], dtype=torch.float32)
    el2 = float((lv ** 2).mean())
    act = torch.ones(B, D, dtype=torch.bool, device=dev)
    x = torch.zeros(B, D, device=dev)
    ar = torch.arange(B, device=dev)
    eye = torch.eye(D, device=dev)
    nst = D if per == 'real' else Nt
    for _ in range(nst):
        Hm = H * act[:, None, :].float()
        G = Hm.transpose(1, 2) @ Hm
        P = torch.linalg.inv(G + (b['N0'] / 2) / el2 * eye)
        mse = torch.diagonal(P, dim1=-2, dim2=-1)
        if per == 'complex':
            mse = mse[:, :Nt] + mse[:, Nt:]
            mse = torch.where(act[:, :Nt], mse, torch.full_like(mse, float('inf')))
            us = mse.argmin(1)
            js = [us, us + Nt]
        else:
            mse = torch.where(act, mse, torch.full_like(mse, float('inf')))
            js = [mse.argmin(1)]
        z = torch.einsum('bij,bj->bi', P @ Hm.transpose(1, 2), y)
        mu = torch.diagonal(P @ G, dim1=-2, dim2=-1)
        for j in js:
            xj = quantize_levels(z[ar, j] / mu[ar, j], M)
            x[ar, j] = xj
            y = y - H[ar, :, j] * xj[:, None]
            act[ar, j] = False
    return x


def ising_delta_at(b, xg, K=1):
    """dDI (Singh et al. 2024 Eqs. 11-16) around given integer levels xg (B, D) with search space D_K (2K spins per
    real dimension, T = 1_(1x2K) (x) I): h = 2 T^T H^T ybar, J = -offdiag(T^T H^T H T), ybar = y - H xg, scaled into
    [-1, 1] by the largest magnitude; candidates xg + T s clipped to the constellation (spins_to_levels_delta)."""
    H, y = b['H'], b['y']
    D = H.shape[-1]
    I_ = torch.eye(D, device=H.device)
    T = torch.cat([I_] * (2 * K), dim=1)
    yb = y - torch.einsum('bij,bj->bi', H, xg)
    HT = H @ T
    h = 2 * torch.einsum('bij,bi->bj', HT, yb)
    Q = HT.transpose(1, 2) @ HT
    J = -(Q - torch.diag_embed(torch.diagonal(Q, dim1=-2, dim2=-1)))
    scale = torch.maximum(h.abs().amax(-1), J.abs().flatten(1).amax(-1)).clamp_min(1e-12)
    h0 = h / scale[:, None]
    J = J / scale[:, None, None]
    sP = torch.cat([torch.ones(h0.shape[0], D, device=H.device), -torch.ones(h0.shape[0], D, device=H.device)] * K, dim=1)
    return dict(h=h0, h0=h0, J=J, sP=sP, T=T, scale=scale, r=0.0, xq=xg, K=K, delta=True)


def mdi_radius(b, xg, Rmax, heuristic='mean'):
    """Search radius of Singh et al. 2024 Sec. IV-B: Gamma = 2 ||ybar^T H|| / lambda (lambda the mean, max or min
    eigenvalue of H^T H); R = omega if 2 omega <= Gamma (Eq. 22), else the R with Gamma - 2 < 2R <= Gamma (Eq. 23);
    capped at Rmax. 2 omega is the largest difference between I/Q components (2 for QPSK, 6 for 16-QAM)."""
    H = b['H']
    lv = PAM[b['M']]['levels']
    omega = (lv[-1] - lv[0]) // 2
    yb = b['y'] - torch.einsum('bij,bj->bi', H, xg)
    g = torch.einsum('bij,bi->bj', H, yb).norm(dim=-1)
    G = H.transpose(1, 2) @ H
    if heuristic == 'mean':
        lam = torch.diagonal(G, dim1=-2, dim2=-1).mean(-1)
    else:
        ev = torch.linalg.eigvalsh(G.double()).float()
        lam = ev[:, -1] if heuristic == 'max' else ev[:, 0].clamp_min(1e-12)
    Gam = 2 * g / lam
    R = torch.where(2 * omega <= Gam, torch.full_like(Gam, float(omega)), torch.floor(Gam / 2))
    return R.clamp(0, Rmax).long(), Gam


def subset(b, idx):
    out = dict(b)
    for k in ('H', 'y', 'l'):
        out[k] = b[k][idx]
    return out


@torch.no_grad()
def mdi(b, solver, Ns, Rmax, S, guesses=('mmse', 'sic'), heuristic='mean', sic_per='real', na_round='ceil',
        z_mmse=None, stats=None):
    """Multi-stage delta Ising MIMO (MDI-MIMO; Singh et al., IEEE TWC 2024, Sec. IV-C steps 1-10). solver(I, na, K)
    returns per-anneal candidate spins (n, na, 2K D). Per stage and guess g the radius R_g (mdi_radius); sub-problems
    (g, K = 1..R_g) each get Ns / (R1 + R2) anneals (rounded up: unpublished, to the baseline's advantage); each guess is
    replaced by its best candidate by ||y - Hx||^2 (the guess included); the output is the better guess after S stages.
    stats (dict) accumulates anneals and spin-updates per instance."""
    M = b['M']
    B, D = b['H'].shape[0], b['H'].shape[-1]
    dev = b['H'].device
    if z_mmse is None:
        z_mmse, Ai, _ = mmse(b)
    cur = {}
    for g in guesses:
        cur[g] = quantize_levels(z_mmse / _mu(b, z_mmse), M) if g == 'mmse' else mmse_sic(b, per=sic_per)
    ann = torch.zeros(B, device=dev)
    for st in range(S):
        R = {g: mdi_radius(b, cur[g], Rmax, heuristic)[0] for g in guesses}
        tot = sum(R[g] for g in guesses)
        if int(tot.max()) == 0:
            break
        nxt = {}
        for g in guesses:
            bl, bd = cur[g].clone(), dist(b, cur[g][:, None, :])[:, 0]
            for K in range(1, Rmax + 1):
                need = R[g] >= K
                if not bool(need.any()):
                    continue
                for t in torch.unique(tot[need]).tolist():
                    idx = torch.nonzero(need & (tot == t)).flatten()
                    na = math.ceil(Ns / t) if na_round == 'ceil' else max(1, Ns // t)
                    sb = subset(b, idx)
                    I = ising_delta_at(sb, cur[g][idx], K)
                    Ssp = solver(I, na, K)
                    Lc = spins_to_levels_delta(Ssp, I, M)
                    dd = dist(sb, Lc)
                    dm, im = dd.min(1)
                    better = dm < bd[idx]
                    bd[idx] = torch.where(better, dm, bd[idx])
                    bl[idx] = torch.where(better[:, None], Lc[torch.arange(len(idx), device=dev), im], bl[idx])
                    ann[idx] += na
            nxt[g] = bl
        cur = nxt
    if stats is not None:
        stats['anneals'] = stats.get('anneals', 0.0) + float(ann.sum())
        stats['n'] = stats.get('n', 0) + B
    allc = torch.stack([cur[g] for g in guesses], 1)
    d = dist(b, allc)
    return allc[torch.arange(B, device=dev), d.argmin(1)]
