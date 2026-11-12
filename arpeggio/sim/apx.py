"""ap_ber_20261024 helpers (PROTOCOL.md): device-independent draws, the MDI wrapper with search-region diagnostics,
every detector of the Table II rerun, and the ablation variants. The existing code (mimo, anefx, ahcfx, pimi, tree,
mdi_solvers in <SCRATCH>/mimo_ising_20261016/src) is imported read-only and reused unchanged; only new
variants live here.

Draws: channel, symbols and noise come from a CPU torch.Generator seeded by (seed, SNR, batch index), so that every
method and every GPU (B200 or RTX 5090) sees bit-identical channel uses (CUDA generators differ across devices).
Solver random numbers come from a per-method CUDA generator (PyTorch solvers) or counter-based Philox (kernels)."""
import math
import os

import numpy as np
import torch

import mimo
import pimi
import tree

torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

SHAPES = {'x16': dict(nt=16, M=16, mdi=dict(Rmax=3, S=8, guesses=('mmse', 'sic')), Ns_pub=64),
          'x32': dict(nt=32, M=16, mdi=dict(Rmax=3, S=8, guesses=('mmse', 'sic')), Ns_pub=128),
          'q16': dict(nt=16, M=4, mdi=dict(Rmax=1, S=1, guesses=('mmse',)), Ns_pub=64),
          'q32': dict(nt=32, M=4, mdi=dict(Rmax=1, S=1, guesses=('mmse',)), Ns_pub=64)}
MA = dict(Sk=128, t0=0.3, t1=0.3, q=0.4, kappa=0.0)                       # frozen MDI schedule (milestone B)
# one-stage schedules exactly as in the paper's Table II row "Antiphase^a" (data/*.jsonl records)
ANED = {'x16': dict(S=256, t0=0.3, t1=0.3, q=0.4, kappa=0.0, phases=2),
        'x32': dict(S=256, t0=0.3, t1=0.2, q=0.4, kappa=0.3, phases=2)}
ANERI = {'q16': dict(S=128, t0=0.7, t1=0.5, q=0.6, kappa=0.0),
         'q32': dict(S=128, t0=0.5, t1=0.4, q=0.4, kappa=0.0)}
KAPPA_ONS = 0.3
SD_CAP1, SD_CAP2 = 2_000_000, 50_000_000


def draw_seed(seed, snr, bi):
    return seed * 1_000_003 + int(round(snr * 100)) * 10_007 + bi


def draw(seed, snr, bi, B, nt, M, dev='cuda'):
    """mimo.make_batch's model and random-number order (levels, Re H, Im H, noise) on a CPU generator; y is formed in
    float64 and rounded to float32 once, because float32 CPU products differ in the last bit between hosts (Intel vs
    AMD BLAS paths; PROTOCOL.md 2, E0). Returns the same dict as mimo.make_batch, on device dev."""
    g = torch.Generator(device='cpu'); g.manual_seed(draw_seed(seed, snr, bi))
    a = mimo.PAM[M]['a']
    lv = torch.tensor(mimo.PAM[M]['levels'], dtype=torch.float32)
    l = lv[torch.randint(0, len(lv), (B, 2 * nt), generator=g)]
    Hc = torch.complex(torch.randn(B, nt, nt, generator=g), torch.randn(B, nt, nt, generator=g)) / math.sqrt(2)
    H = mimo.complex_to_real(Hc) * a
    N0 = nt * 1.0 / (10 ** (snr / 10))
    n = torch.randn(B, 2 * nt, generator=g) * math.sqrt(N0 / 2)
    y = ((H.double() * l.double()[:, None, :]).sum(-1) + n.double()).float()
    return dict(H=H.to(dev), y=y.to(dev), l=l.to(dev), N0=N0, M=M, Nt=nt, Nr=nt)


def dist_true(b):
    return ((b['y'] - torch.einsum('bij,bj->bi', b['H'], b['l'])) ** 2).sum(-1)


def dist_of(b, l):
    return ((b['y'] - torch.einsum('bij,bj->bi', b['H'], l)) ** 2).sum(-1)


def biterr_per_use(b, lh):
    bt = mimo.levels_to_bits(b['l'], b['M'])
    bh = mimo.levels_to_bits(lh, b['M'])
    return (bt != bh).sum(-1).to(torch.int32)


# ---------------------------------------------------------------- MDI wrapper with diagnostics
def mdi_radius_om(b, xg, Rmax, heuristic='mean', omega=None):
    """mimo.mdi_radius with an optional override of omega (2 omega = largest I/Q level difference; the MDI-MIMO text
    says 2 omega = 4 for 16-QAM where its definition gives 6: ambiguity test, PROTOCOL.md 8)."""
    if omega is None:
        return mimo.mdi_radius(b, xg, Rmax, heuristic)
    H = b['H']
    yb = b['y'] - torch.einsum('bij,bj->bi', H, xg)
    g = torch.einsum('bij,bi->bj', H, yb).norm(dim=-1)
    lam = torch.diagonal(H.transpose(1, 2) @ H, dim1=-2, dim2=-1).mean(-1)
    Gam = 2 * g / lam
    R = torch.where(2 * omega <= Gam, torch.full_like(Gam, float(omega)), torch.floor(Gam / 2))
    return R.clamp(0, Rmax).long(), Gam


@torch.no_grad()
def mdi_diag(b, solver, Ns, Rmax, S, guesses=('mmse', 'sic'), heuristic='mean', sic_per='real', na_round='ceil',
             z_mmse=None, stats=None, to_levels=None, omega=None):
    """mimo.mdi (Singh et al. 2024 Sec. IV-C), statement for statement, plus per-instance diagnostics:
    inbox_any: the transmitted vector lay inside the box |x - x_g|_inf <= 2 R_g of a guess g that was searched (R_g >= 1)
    at some stage (the K = R_g sub-problem's box contains those of K < R_g); inbox_s1: the same at stage 1 only;
    R1: stage-1 radii per guess; nst: stages with a non-zero radius for this instance. to_levels(S, I, M): candidate
    levels of the solver's spins (default mimo.spins_to_levels_delta, clipped; PIMI uses its own slicing)."""
    M = b['M']
    B, D = b['H'].shape[0], b['H'].shape[-1]
    dev = b['H'].device
    tl = to_levels or mimo.spins_to_levels_delta
    truth = b['l']
    if z_mmse is None:
        z_mmse, Ai, _ = mimo.mmse(b)
    cur = {}
    for g in guesses:
        cur[g] = mimo.quantize_levels(z_mmse / mimo._mu(b, z_mmse), M) if g == 'mmse' else mimo.mmse_sic(b, per=sic_per)
    ann = torch.zeros(B, device=dev)
    inbox_any = torch.zeros(B, dtype=torch.bool, device=dev)
    inbox_s1 = torch.zeros(B, dtype=torch.bool, device=dev)
    R1 = torch.zeros(B, len(guesses), dtype=torch.int8, device=dev)
    nst = torch.zeros(B, dtype=torch.int8, device=dev)
    for st in range(S):
        R = {g: mdi_radius_om(b, cur[g], Rmax, heuristic, omega)[0] for g in guesses}
        tot = sum(R[g] for g in guesses)
        for gi, g in enumerate(guesses):
            inb = (R[g] >= 1) & ((truth - cur[g]).abs().amax(-1) <= 2 * R[g])
            inbox_any |= inb
            if st == 0:
                inbox_s1 |= inb
                R1[:, gi] = R[g].to(torch.int8)
        nst += (tot > 0).to(torch.int8)
        if int(tot.max()) == 0:
            break
        nxt = {}
        for g in guesses:
            bl, bd = cur[g].clone(), mimo.dist(b, cur[g][:, None, :])[:, 0]
            for K in range(1, Rmax + 1):
                need = R[g] >= K
                if not bool(need.any()):
                    continue
                for t in torch.unique(tot[need]).tolist():
                    idx = torch.nonzero(need & (tot == t)).flatten()
                    na = math.ceil(Ns / t) if na_round == 'ceil' else max(1, Ns // t)
                    sb = mimo.subset(b, idx)
                    I = mimo.ising_delta_at(sb, cur[g][idx], K)
                    Ssp = solver(I, na, K)
                    Lc = tl(Ssp, I, M)
                    dd = mimo.dist(sb, Lc)
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
    d = mimo.dist(b, allc)
    lh = allc[torch.arange(B, device=dev), d.argmin(1)]
    return lh, dict(inbox_any=inbox_any, inbox_s1=inbox_s1, R1=R1, nst=nst, ann=ann)


# ---------------------------------------------------------------- solver variants (ablation, item 5)
def gdiag(I, K):
    """G~_mm (coefficient-scaled diagonal of H^T H) per spin, from the copy-0/copy-1 coupling J[m, D + m] = -G~_mm."""
    N = I['J'].shape[-1]
    D = N // (2 * K)
    g = -torch.diagonal(I['J'][:, :D, D:2 * D], dim1=-2, dim2=-1)          # (B, D)
    return g.repeat(1, 2 * K)                                             # (B, N), copy-major like the spins


@torch.no_grad()
def anechoic_ext(I, R, S, T, q, phases=1, dil=0.0, track='best', gen=None):
    """mimo.anechoic at kappa = 0 (constant T), with a per-spin pinning q (scalar or (B, N)) and optional random
    dilution: each spin may flip at a half-step with probability dil (dil = 0: no dilution). Same random-number
    order as mimo.anechoic for the start and the decisions; the dilution mask is drawn after the decision noise."""
    h, J = I['h'], I['J']
    B, N = h.shape
    dev = h.device
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    qv = q[:, None, :] if torch.is_tensor(q) else q
    best_s, best_e = s.clone(), torch.full((B, R), float('inf'), device=dev)
    idx = torch.arange(N, device=dev) // (N // phases) if phases > 1 else None
    for k in range(S):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        z = s * u + qv
        rr = (torch.rand(B, R, N, generator=gen, device=dev) - 0.5) * 4 * T
        flip = z < rr
        if phases > 1:
            flip = flip & (idx == (k % phases))
        if dil > 0:
            flip = flip & (torch.rand(B, R, N, generator=gen, device=dev) < dil)
        s = torch.where(flip, -s, s)
        if track == 'best':
            e = mimo.energy0(s, I['h0'], J)
            better = e < best_e
            best_e = torch.where(better, e, best_e)
            best_s = torch.where(better[..., None], s, best_s)
    return best_s if track == 'best' else s


@torch.no_grad()
def sa_seq(I, R, sweeps, T0, T1, K, gen=None, count=None):
    """Sequential single-spin Metropolis simulated annealing (our baseline arm): spins visited in index order, flip
    accepted with probability min(1, exp(-dE / T)), dE = 2 s_i u_i in the same scaled energy units as Antiphase;
    geometric T0 -> T1 over the sweeps; random start; fields updated per accepted flip; the lowest-energy state is
    tracked after every block of D = N / 2K spin visits (the granularity of Antiphase's half-steps).
    count (A5.3c, optional): dict accumulating, per K, accepted flips, decisions (sweeps * N per anneal) and anneals;
    it only reads acc, so the random stream and the result are unchanged."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    D = N // (2 * K)
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = mimo.energy0(s, h0, J)
    best_s, best_e = s.clone(), E.clone()
    Ts = mimo.geom(T0, T1, sweeps, dev).tolist()
    Jt = J.transpose(1, 2).contiguous()                                    # Jt[b, i, :] = J[b, :, i]
    nfl = torch.zeros((), dtype=torch.float64, device=dev) if count is not None else None
    for sw in range(sweeps):
        T = Ts[sw]
        rnd = torch.rand(B, R, N, generator=gen, device=dev)
        for i in range(N):
            si = s[..., i]
            dE = 2 * si * u[..., i]
            acc = (dE <= 0) | (rnd[..., i] < torch.exp(-dE / T))
            if nfl is not None:
                nfl += acc.sum()
            delta = torch.where(acc, -2 * si, torch.zeros_like(si))
            u += 2 * delta[..., None] * Jt[:, None, i, :]
            s[..., i] = si + delta
            E += torch.where(acc, dE, torch.zeros_like(dE))
            if (i + 1) % D == 0:
                better = E < best_e
                best_e = torch.where(better, E, best_e)
                best_s = torch.where(better[..., None], s, best_s)
    if count is not None:
        d = count.setdefault(K, dict(flips=0.0, decisions=0, anneals=0, N=N))
        d['flips'] += float(nfl)
        d['decisions'] += B * R * N * sweeps
        d['anneals'] += B * R
    return best_s


@torch.no_grad()
def sym_hb(I, R, L, T, K, q=0.0, mode='prop', gen=None, dil=0.0):
    """Symbol-level synchronous heat-bath on d (our own variant, p-dit style): one multi-level variable per real
    dimension, d_m in {-2K, ..., 2K} (steps of 2 = one constellation level), all dimensions updated at once from the
    others' current values, L synchronous steps (= Antiphase's half-steps). mode 'prop': each dimension proposes a
    uniformly random +-1-level move (rejected outside the range), accepted with the heat-bath probability
    1 / (1 + exp((dE + 2q) / T)); mode 'win': each dimension samples {d - 2, d, d + 2} from exp(-(dE + 2q [if moving]) / T).
    q is a stay bias with the same meaning as SCA's pinning (flip iff s u + q < r compares (dE + 2q) / 2 with r).
    Start: d = sum of 2K random spins (Antiphase's start law). The lowest-energy state visited is returned as 2K-copy
    spins (d = sum of copies)."""
    h0, J = I['h0'], I['J']
    B, N = h0.shape
    dev = h0.device
    P = 2 * K
    D = N // P
    G = -J[:, :D, D:2 * D]                                                # (B, D, D) incl. diagonal G~_mm
    Gd = torch.diagonal(G, dim1=-2, dim2=-1)[:, None, :]                  # (B, 1, D)
    bt = (h0[:, :D] / 2)[:, None, :]                                       # (B, 1, D)
    s0 = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    d = s0.reshape(B, R, P, D).sum(2)
    energy = lambda d_: (d_ * torch.einsum('bij,brj->bri', G, d_)).sum(-1) - 2 * (bt * d_).sum(-1)
    E = energy(d)
    best_d, best_e = d.clone(), E.clone()
    inf = torch.tensor(float('inf'), device=dev)
    for k in range(L):
        g = torch.einsum('bij,brj->bri', G, d)
        dEp = 4 * g + 4 * Gd - 4 * bt + 2 * q                              # move +2 (one level up), stay bias included
        dEm = -4 * g + 4 * Gd + 4 * bt + 2 * q                             # move -2
        dEp = torch.where(d + 2 > P, inf, dEp)
        dEm = torch.where(d - 2 < -P, inf, dEm)
        if mode == 'prop':
            up = torch.rand(B, R, D, generator=gen, device=dev) < 0.5
            dE = torch.where(up, dEp, dEm)
            acc = torch.rand(B, R, D, generator=gen, device=dev) < torch.sigmoid(-dE / T)
            step = torch.where(acc, torch.where(up, 2.0, -2.0), 0.0)
        else:
            pr = torch.softmax(torch.stack([torch.zeros_like(dEp), -dEp / T, -dEm / T], -1), -1)
            u = torch.rand(B, R, D, generator=gen, device=dev)
            c1 = pr[..., 0]
            step = torch.where(u < c1, 0.0, torch.where(u < c1 + pr[..., 1], 2.0, -2.0))
        if dil > 0:                                                        # control b2: each dimension eligible w.p. dil
            step = torch.where(torch.rand(B, R, D, generator=gen, device=dev) < dil, step, torch.zeros_like(step))
        d = d + step
        E = energy(d)
        better = E < best_e
        best_e = torch.where(better, E, best_e)
        best_d = torch.where(better[..., None], d, best_d)
    npos = ((best_d + P) / 2).round().long()                               # copies at +1
    c = torch.arange(P, device=dev)[None, None, :, None]
    s = torch.where(c < npos[:, :, None, :], 1.0, -1.0)                    # (B, R, P, D)
    return s.reshape(B, R, N)


def colour_classes(N, P, mode, m, dev):
    """Index tensors of the colour classes (PROTOCOL_A5.md, A5b). Spins are copy-major (copy p holds dims p D .. p D + D - 1,
    D = 2 Nt: Nt in-phase then Nt quadrature dims). mode 'copy': m = 0 -> one class (all spins, fully synchronous);
    m >= 1 -> c = m P classes, class (p, g) = copy p, users [g Nt/m, (g+1) Nt/m) with BOTH their I and Q dims (columns m
    and m + Nt of the real lift are orthogonal, so at m = Nt every class has two non-interacting spins: c = N/2 is an
    exact chromatic sweep); class order k -> (p = k mod P, g = (k // P) mod m). mode 'dim' (control b1): P classes, class g
    = dims [g D/P, (g+1) D/P) of ALL copies (copies in phase, activity 1/P)."""
    D = N // P
    Nt = D // 2
    ar = lambda a, w: torch.arange(a, a + w, device=dev)
    if mode == 'dim':                                                      # uneven split when P does not divide D
        bnd = [round(g * D / P) for g in range(P + 1)]
        return [torch.cat([ar(p * D + bnd[g], bnd[g + 1] - bnd[g]) for p in range(P)]) for g in range(P)]
    if m == 0:
        return [ar(0, N)]
    w = Nt // m
    cls = []
    for k in range(m * P):
        p, g = k % P, (k // P) % m
        cls.append(torch.cat([ar(p * D + g * w, w), ar(p * D + Nt + g * w, w)]))
    return cls


@torch.no_grad()
def anechoic_classes(I, R, T, q, classes, Sk=128, gen=None, count=None):
    """Antiphase's own rule (flip iff s u + q < r, r ~ U[-2T, 2T)), constant T, pinning q, best of trajectory, random start,
    over the given colour classes visited cyclically; equal decisions per spin: L = Sk c steps (c = number of classes),
    i.e. Sk c dependent steps per anneal. Fields updated incrementally from the flipped spins (re-synchronised once per
    sweep); E = -s.(u + h0) / 2. count: optional dict accumulating flips, steps and anneals per K (K from 2K = P)."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    c = len(classes)
    L = Sk * c
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = -(s * (u + h0[:, None, :])).sum(-1) / 2
    best_s, best_e = s.clone(), E.clone()
    Jc = [J[:, :, ix].contiguous() for ix in classes]
    nfl = 0.0
    for k in range(L):
        ix = classes[k % c]
        ss, uu = s[..., ix], u[..., ix]
        z = ss * uu + q
        rr = (torch.rand(B, R, len(ix), generator=gen, device=dev) - 0.5) * 4 * T
        ds = torch.where(z < rr, -2 * ss, torch.zeros_like(ss))
        s[..., ix] = ss + ds
        if count is not None:
            nfl += float((ds != 0).sum())
        if (k + 1) % c == 0:
            u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        else:
            u = u + 2 * torch.einsum('bij,brj->bri', Jc[k % c], ds)
        E = -(s * (u + h0[:, None, :])).sum(-1) / 2
        better = E < best_e
        best_e = torch.where(better, E, best_e)
        best_s = torch.where(better[..., None], s, best_s)
    if count is not None:
        K = count.get('_K')
        d = count.setdefault(K, dict(flips=0.0, steps=0, anneals=0))
        d['flips'] += nfl; d['steps'] += L * B * R; d['anneals'] += B * R
    return best_s


def anechoic_colour(I, R, T, q, P, m, Sk=128, gen=None, count=None, mode='copy'):
    if count is not None:
        count['_K'] = P // 2
    return anechoic_classes(I, R, T, q, colour_classes(I['h'].shape[1], P, mode, m, I['h'].device), Sk, gen, count)


@torch.no_grad()
def snowball_par(I, R, iters, T0, T1, gen=None):
    """A5d "parallel-trial single flip" (rejection-free single-flip selection; e.g. Fujitsu DA parallel trial, BKL; the
    roulette-wheel form follows arXiv:2601.21058 Sec. "Parallel Markov Chain Monte Carlo (Roulette-Wheel)", Alg. 1):
    every iteration evaluates the Glauber flip probabilities p_i = 1 / (1 + exp(dE_i / T)), dE_i = 2 s_i u_i, of all spins
    in parallel, selects ONE spin with probability p_i / sum p (roulette wheel) and flips it deterministically
    (rejection-free, asynchronous single-spin update), updates the fields incrementally; if sum p is not positive and
    finite it falls back to one random-scan single-spin Glauber step. Geometric cooling T0 -> T1 over the iterations;
    random start. Inside MDI the lowest-energy visited state is returned (as for every variant here; Snowball itself
    returns its final state)."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = -(s * (u + h0[:, None, :])).sum(-1) / 2
    best_s, best_e = s.clone(), E.clone()
    Ts = mimo.geom(T0, T1, iters, dev).tolist()
    bi = torch.arange(B, device=dev)[:, None]
    for t in range(iters):
        dE = 2 * s * u
        p = torch.sigmoid(-dE / Ts[t])
        tot = p.sum(-1, keepdim=True)
        ok = (tot > 0) & torch.isfinite(tot)
        r = torch.rand(B, R, 1, generator=gen, device=dev)
        idx = (p.cumsum(-1) < r * tot).sum(-1, keepdim=True).clamp(max=N - 1)
        ridx = torch.randint(0, N, (B, R, 1), generator=gen, device=dev)            # fallback: random scan
        racc = torch.rand(B, R, 1, generator=gen, device=dev) < p.gather(-1, ridx)
        idx = torch.where(ok, idx, ridx)
        do = ok | racc
        si = s.gather(-1, idx)
        dEi = dE.gather(-1, idx)
        delta = torch.where(do, -2 * si, torch.zeros_like(si))
        s.scatter_(-1, idx, si + delta)
        u = u + 2 * delta * J[bi, idx[..., 0]]                                     # J symmetric: column = row
        E = E + torch.where(do, dEi, torch.zeros_like(dEi))[..., 0]
        better = E < best_e
        best_e = torch.where(better, E, best_e)
        best_s = torch.where(better[..., None], s, best_s)
    return best_s


def pimi_solver(I, na, K, steps, M, gen):
    """PIMI's update (pimi.run, bit-identical to the authors' pbits_im.py rule, unchanged) on an MDI delta sub-problem:
    J symmetrised, h = h0 / 2 as in pimi.problem; schedule A (16-QAM) or B (QPSK) of pimi.sched_name; na trials from
    random spins; returns the final spins of every trial (PIMI's own output rule; MDI then selects by ||y - Hx||^2)."""
    J = (I['J'] + I['J'].transpose(1, 2)) / 2
    P = pimi.quantize(J, I['h0'] / 2, I['xq'])
    beta, gamma = pimi.SCHED['A' if M == 16 else 'B']
    S, _ = pimi.pimi_torch(P, steps, na, gen, beta=beta, gamma=gamma)
    return S.to(torch.float32)


def pimi_levels(S, I, M):
    """PIMI's reconstruction x = x_g + T s, sliced to the constellation (its spins can be 0)."""
    D = I['xq'].shape[-1]
    d = S.reshape(*S.shape[:-1], 2 * I['K'], D).sum(-2)
    return pimi.slice_levels(I['xq'][:, None, :] + d, M)


# ---------------------------------------------------------------- detectors
class Ctx:
    """Per-process context: kernels (loaded lazily), tuned ablation settings, counters."""

    def __init__(self, tuned=None):
        self.kh = None
        self.ka = None
        self.tuned = tuned or {}
        self.calls = 0

    def ahc_kernel(self):
        if self.kh is None:
            import ahcfx
            self.kh = ahcfx.AhcKernel(os.environ['AHC_CUBIN'])
        return self.kh

    def ane_kernel(self):
        if self.ka is None:
            import anefx
            self.ka = anefx.Kernel(os.environ['ANE_CUBIN'])
        return self.ka


def mdi_solver_for(method, shape, gs, ctx):
    """(solver(I, na, K), to_levels or None, Ns) for an MDI method name."""
    M = SHAPES[shape]['M']
    if method.startswith('mdiahck'):                                      # AHC CUDA kernel (identical bit errors to mimo.ahc)
        import ahcfx
        kh = ctx.ahc_kernel()

        def f(I, na, K):
            B, N = I['h0'].shape
            x0, e0 = ahcfx.start_state(B, na, N + 1, gs, I['h0'].device)
            return kh.ahc(I, x0, e0)[0].float()
        return f, None, int(method[7:])
    if method.startswith('mdiahc'):
        return (lambda I, na, K: mimo.ahc(I, na, gen=gs)), None, int(method[6:])
    if method.startswith('mdiane'):
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, MA['t0'], MA['t1'], MA['q'], kappa=0.0, gen=gs,
                                               phases=2 * K)), None, int(method[6:])
    v, Ns = method[4:].rsplit('_', 1)                                     # abl_<variant>_<Ns>
    Ns = int(Ns)
    if v.startswith('qt_'):                                                # grid: abl_qt_<a|s>_<q>_<T>_<Ns> (mechanism)
        _, al, qq, TT = v.split('_')
        qq, TT = float(qq), float(TT)
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, TT, TT, qq, gen=gs,
                                               phases=2 * K if al == 'a' else 1)), None, Ns
    if v.startswith('qdimc_'):                                             # grid: abl_qdimc_<c>_<q0>_<T>_<Ns>, no alternation
        _, cc, q0, TT = v.split('_')
        cc, q0, TT = float(cc), float(q0), float(TT)
        return (lambda I, na, K: anechoic_ext(I, na, MA['Sk'] * 2 * K, TT, q0 + cc * 2 * K * gdiag(I, K), phases=1,
                                              gen=gs)), None, Ns
    if v.startswith('sat_'):                                               # grid: abl_sat_<T0>_<T1>_<Ns>
        _, T0, T1 = v.split('_')
        return (lambda I, na, K: sa_seq(I, na, MA['Sk'], float(T0), float(T1), K, gen=gs)), None, Ns
    if v.startswith('symt_'):                                              # grid: abl_symt_<prop|win>_<T>_<q>_<Ns>
        _, md, TT, qq = v.split('_')
        return (lambda I, na, K: sym_hb(I, na, MA['Sk'] * 2 * K, float(TT), K, q=float(qq), mode=md, gen=gs)), None, Ns
    T, q = MA['t0'], MA['q']
    if v.startswith('col_'):                                               # A5b: abl_col_<m>_<Ns>, frozen T 0.3, q 0.4
        mm = int(v.split('_')[1])
        return (lambda I, na, K: anechoic_colour(I, na, MA['t0'], MA['q'], 2 * K, mm, gen=gs)), None, Ns
    if v.startswith('colt_'):                                              # A5b tuning: abl_colt_<m>_<q>_<T>_<Ns>
        _, mm, qq, TT = v.split('_')
        return (lambda I, na, K: anechoic_colour(I, na, float(TT), float(qq), 2 * K, int(mm), gen=gs)), None, Ns
    if v.startswith('colk_'):                                              # A5b per-c tuned: abl_colk_<m>_<Ns>
        mm = v.split('_')[1]
        tc = ctx.tuned['col'][shape][mm]
        return (lambda I, na, K: anechoic_colour(I, na, tc['T'], tc['q'], 2 * K, int(mm), gen=gs)), None, Ns
    if v.startswith('dimt_') or v == 'dimk':                               # control b1: P colours by dimension
        if v == 'dimk':
            qq, TT = ctx.tuned['dim']['q'], ctx.tuned['dim']['T']
        else:
            _, qq, TT = v.split('_'); qq, TT = float(qq), float(TT)
        return (lambda I, na, K: anechoic_colour(I, na, TT, qq, 2 * K, 0, gen=gs, mode='dim')), None, Ns
    if v.startswith('symdt_') or v == 'symdk':                             # control b2: (x) diluted to 1/P
        if v == 'symdk':
            TT, qq = ctx.tuned['symd']['T'], ctx.tuned['symd']['q']
        else:
            _, TT, qq = v.split('_'); TT, qq = float(TT), float(qq)
        return (lambda I, na, K: sym_hb(I, na, MA['Sk'] * 2 * K, TT, K, q=qq, mode='prop', gen=gs, dil=1.0 / (2 * K))), None, Ns
    if v.startswith('sao_'):                                               # A5.3b: old-pick sweep series abl_sao_<sweeps>_<Ns>
        sw = int(v.split('_')[1])
        ts = ctx.tuned['sa']
        return (lambda I, na, K: sa_seq(I, na, sw, ts['T0'], ts['T1'], K, gen=gs)), None, Ns
    if v.startswith('sas_'):                                               # A5a sweep series: abl_sas_<sweeps>_<Ns>
        sw = int(v.split('_')[1])
        ts = ctx.tuned['sa2']
        return (lambda I, na, K: sa_seq(I, na, sw, ts['T0'], ts['T1'], K, gen=gs)), None, Ns
    if v == 'sa2':                                                         # A5a: re-tuned SA, 128 sweeps
        ts = ctx.tuned['sa2']
        return (lambda I, na, K: sa_seq(I, na, MA['Sk'], ts['T0'], ts['T1'], K, gen=gs)), None, Ns
    if v.startswith('qdimk'):                                              # (iv) re-tuned per point
        tq = ctx.tuned['qdim_pp'][shape]
        return (lambda I, na, K: anechoic_ext(I, na, MA['Sk'] * 2 * K, tq['T'], tq['q0'] + tq['c'] * 2 * K * gdiag(I, K),
                                              phases=1, gen=gs)), None, Ns
    if v.startswith('pt'):                                                 # A5d parallel-trial single flip
        # abl_ptt_<cyc|fl>_<T0>_<T1>_<Ns> (tuning), abl_pt<c|f>_<Ns> (P1-tuned), abl_pt<c|f>p_<Ns> (tuned at this point)
        if v.startswith('ptt_'):
            _, bud, T0, T1 = v.split('_'); T0, T1 = float(T0), float(T1)
        elif v.startswith('pt2'):                                          # A5.2: abl_pt2<c|f>[p]_<Ns>, extended-grid picks
            bud = 'cyc' if v[3] == 'c' else 'fl'
            key = 'pt2_' + bud + (('_' + shape) if v.endswith('p') else '')
            T0, T1 = ctx.tuned[key]['T0'], ctx.tuned[key]['T1']
        else:
            bud = 'cyc' if v[2] == 'c' else 'fl'
            key = 'pt_' + bud + (('_' + shape) if v.endswith('p') else '')
            T0, T1 = ctx.tuned[key]['T0'], ctx.tuned[key]['T1']
        phi = ctx.tuned['flip_phi'][shape]

        def nit(K, N):
            L = MA['Sk'] * 2 * K
            F = phi[str(K)] * L
            if bud == 'fl':
                return max(1, int(round(F)))
            return max(1, int(round((L + F) / (1 + math.ceil(math.log2(N))))))
        return (lambda I, na, K: snowball_par(I, na, nit(K, I['h'].shape[1]), T0, T1, gen=gs)), None, Ns
    if v == 'noalt':                                                       # (ii) alternation off
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, T, T, q, gen=gs, phases=1)), None, Ns
    if v == 'noaltq0':                                                     # plain synchronous SCA (no pinning, no alternation)
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, T, T, 0.0, gen=gs, phases=1)), None, Ns
    if v == 'q0':                                                          # (iii) q = 0
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, T, T, 0.0, gen=gs, phases=2 * K)), None, Ns
    if v == 'qdim':                                                        # (iv) q_m = q0 + c 2K G~_mm, no alternation
        tq = ctx.tuned['qdim']
        return (lambda I, na, K: anechoic_ext(I, na, MA['Sk'] * 2 * K, tq['T'], tq['q0'] + tq['c'] * 2 * K * gdiag(I, K),
                                              phases=1, gen=gs)), None, Ns
    if v == 'dil':                                                         # (v) random dilution p = 1/P
        return (lambda I, na, K: anechoic_ext(I, na, MA['Sk'] * 2 * K, T, q, phases=1, dil=1.0 / (2 * K), gen=gs)), None, Ns
    if v == 'final':                                                       # (vi) final state, not best of trajectory
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, T, T, q, gen=gs, phases=2 * K, track='final')), None, Ns
    if v == 'ons':                                                         # (vii) Onsager kT on (kappa 0.3, milestone D)
        return (lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, T, T, q, kappa=KAPPA_ONS, gen=gs,
                                               phases=2 * K)), None, Ns
    if v == 'pimi':                                                        # (viii) PIMI's update, 128 steps
        return (lambda I, na, K: pimi_solver(I, na, K, MA['Sk'], M, gs)), pimi_levels, Ns
    if v == 'sa':                                                          # (ix) sequential Metropolis SA, 128 sweeps
        ts = ctx.tuned['sa']
        return (lambda I, na, K: sa_seq(I, na, MA['Sk'], ts['T0'], ts['T1'], K, gen=gs)), None, Ns
    if v in ('sym', 'symw'):                                               # (x) symbol-level synchronous heat-bath
        th = ctx.tuned[v]
        md = 'prop' if v == 'sym' else 'win'
        return (lambda I, na, K: sym_hb(I, na, MA['Sk'] * 2 * K, th['T'], K, q=th['q'], mode=md, gen=gs)), None, Ns
    raise ValueError(method)


def detect(method, b, shape, gs, ctx, z=None, extra=None):
    """Returns (levels (B, D), diag dict of per-use tensors or None, info dict)."""
    M = b['M']
    D = b['H'].shape[-1]
    lvl = np.array(mimo.PAM[M]['levels'], np.float64)
    info = {}
    if z is None:
        z, Ai, _ = mimo.mmse(b)
    else:
        Ai = None
    if method == 'mmse':
        return mimo.quantize_levels(z / mimo._mu(b, z), M), None, info
    if method == 'sic':
        return mimo.mmse_sic(b, 'real'), None, info
    if method == 'sicc':                                                   # ambiguity: per-user (complex) SIC ordering
        return mimo.mmse_sic(b, 'complex'), None, info
    if method.startswith('kbest'):
        Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
        out, _ = tree.kbest2(Hn, yn, lvl, int(method[5:]))
        return torch.tensor(out, device=b['H'].device, dtype=torch.float32), None, info
    if method == 'sd':
        Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
        out, nodes, done = tree.sphere_decoder(Hn, yn, lvl, SD_CAP1)
        nd1 = int((~done).sum())
        if nd1:
            ix = np.nonzero(~done)[0]
            out2, nodes2, done2 = tree.sphere_decoder(np.ascontiguousarray(Hn[ix]), np.ascontiguousarray(yn[ix]), lvl, SD_CAP2)
            out[ix] = out2; nodes[ix] = nodes2; done[ix] = done2
        info.update(sd_unfinished_cap1=nd1, sd_unfinished=int((~done).sum()), sd_nodes_mean=float(nodes.mean()))
        dg = dict(uncert=torch.tensor(~done, device=b['H'].device))
        return torch.tensor(out, device=b['H'].device, dtype=torch.float32), dg, info
    lm = mimo.quantize_levels(z / mimo._mu(b, z), M)
    if method == 'aned64':                                                 # one delta stage around MMSE (16-QAM)
        p = ANED[shape]
        Id = mimo.ising_delta(b, z, K=1)
        S_ = mimo.anechoic(Id, 64, p['S'], p['t0'], p['t1'], p['q'], kappa=p['kappa'], gen=gs, phases=p['phases'])
        lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, M), lm)
        inb = (b['l'] - lm).abs().amax(-1) <= 2
        return lh, dict(inbox_any=inb, inbox_s1=inb), info
    if method == 'ane64ri':                                                # one-stage RI-MIMO formulation (QPSK)
        p = ANERI[shape]
        I = mimo.ising(b, z)
        S_ = mimo.anechoic(I, 64, p['S'], p['t0'], p['t1'], p['q'], kappa=p['kappa'], gen=gs)
        lh, _, _ = mimo.select(b, mimo.spins_to_levels(S_, M, D), lm)
        return lh, None, info
    if method.startswith('amb_') or method.startswith('ambt_'):           # ambiguity tests on MDI-AHC: amb[t]_<om2|x0sd|floor>_<Ns>
        v, Ns = method.split('_', 1)[1].rsplit('_', 1)                    # amb_: AHC kernel (B200); ambt_: PyTorch mimo.ahc
        Ns = int(Ns)
        import ahcfx
        x0v = 1e-6 if v == 'x0sd' else ahcfx.DEF['x0_var']
        if method.startswith('ambt_'):
            solver = lambda I, na, K: mimo.ahc(I, na, x0_var=x0v, gen=gs)
        else:
            kh = ctx.ahc_kernel()

            def solver(I, na, K):
                B_, N_ = I['h0'].shape
                x0, e0 = ahcfx.start_state(B_, na, N_ + 1, gs, I['h0'].device, x0_var=x0v)
                return kh.ahc(I, x0, e0)[0].float()
        c = SHAPES[shape]['mdi']
        st = {}
        lh, dg = mdi_diag(b, solver, Ns, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z, stats=st,
                          omega=2 if v == 'om2' else None, na_round='floor' if v == 'floor' else 'ceil')
        info['anneals'] = st['anneals']
        return lh, dg, info
    if method.startswith('mdi') or method.startswith('abl_'):
        solver, tl, Ns = mdi_solver_for(method, shape, gs, ctx)
        c = SHAPES[shape]['mdi']
        st = {}
        lh, dg = mdi_diag(b, solver, Ns, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z, stats=st, to_levels=tl)
        info['anneals'] = st['anneals']
        return lh, dg, info
    raise ValueError(method)
