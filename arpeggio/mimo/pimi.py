"""PIMI, Princeton/Cornell's probabilistic Ising machine with inertia (Zhu et al., arXiv:2604.17109v2), for MIMO detection,
reproduced from the authors' published code (Zenodo 10.5281/zenodo.18215709, record 18318271; milestone D, LEDGER):
- instances (src/def_MIMO.py create_instance): DI-MIMO around the hard (biased) MMSE estimate, D = {-2, 0, 2}, T = [I, I],
  J = -[[G, G], [G, G]] with zero main diagonal (G = H^T H, real lift), h = [h', h'] with h' = 2 H^T (y - H x_mmse),
  scale = max(|J|max, |h|max), J / scale and h / (2 scale); noise per instance from the empirical received power,
  noise_power = mean|H x|^2 / (b Eb/N0); MMSE regulariser noise_power / Es (the code; App. 15 Eq. S47 differs);
- update (src/pbits_im.py, algorithm 'tanh_lut', parallel = True), every quantity in ap_fixed<16,4> emulation
  (src/aux.py FixedPointQuantizer(16, 12): trunc(x 2^12) toward zero, saturated to [-2^15, 2^15 - 1]):
    MVM = q(J s); I = q(beta (MVM + h)); SI = q(2 I); L = q(tanh_lut(SI, 4)); r = q(N(0, 1)); n = q(eta_t r);
    s <- sign(q(L + s + n))              (np.sign: a zero sum gives spin 0)
  tanh_lut (aux.py): x <= -1/2 -> -1, (-1/2, 0] -> -1/3, (0, 1/2] -> 1/3, > 1/2 -> 1;
- schedule: eta_t = sqrt(1 / (5 gamma_t)), gamma_t = linspace(g0, g1, steps), constant beta, two parameter sets in their
  code: A (16-QAM run notebooks, 8x8 and 16x16) beta 2, gamma 0.1 -> 0.999; B (gen_noise.py, the FPGA noise table)
  beta 1, gamma 0.01 -> 0.999. On their own instances A reproduces their published BER for 16-QAM (both sizes) and
  8x8 64-QAM, B for 4-QAM (both sizes) and 16x16 64-QAM (diag_pimi_sched.py; LEDGER); sched_for() applies that;
  32 trials from uniform random spins; fresh N(0, 1) per instance, step, spin and trial;
- output (run notebook): per instance the final state of the trial whose final energy E = -1/2 s^T J s - h^T s (quantised
  J, h) is lowest (first minimum); x = x_mmse + T s, sliced to the nearest constellation point.
Everything below works in integer units of 2^-12 (exact: all values are multiples of 2^-12).

Three solvers share that arithmetic and differ only in where the random numbers come from:
- pimi_torch: PyTorch generators (torch.randn, torch.randint) — the same-framework implementation, timed;
- pimi_fx: Philox4x32-10 (counter (n // 4, spin, trial, instance), output n mod 4, as anefx) indexing a 2^16-entry
  inverse-CDF table of q(N(0, 1)) — the definition that the CUDA kernel (pimi_kernel.cu) reproduces bit for bit;
- pimi_inject: noise and start states given explicitly — used to check bit-identity against the authors' own code."""
import math

import numpy as np
import torch

import anefx
import mimo

FRAC = 12
ONE = 1 << FRAC                      # 4096
QMIN, QMAX = -(1 << 15), (1 << 15) - 1
LUT_INT = (-ONE, -1365, 1365, ONE)   # q(-1), q(-1/3) = trunc(-1365.33), q(1/3), q(1)
BETA = 2.0                           # schedule A (default of the solvers below)
GAMMA = (0.1, 0.999)
SCHED = {'A': (2.0, (0.1, 0.999)), 'B': (1.0, (0.01, 0.999))}
TRIALS = 32


def sched_name(nt, M):
    """The schedule that reproduces the authors' published BER for this panel; 32x32 follows its modulation."""
    if M == 4:
        return 'B'
    if M == 64:
        return 'A' if nt <= 8 else 'B'
    return 'A'


def sched_for(nt, M):
    return SCHED[sched_name(nt, M)]


# ---------------------------------------------------------------- square QAM, per real dimension (generic M)
def levels(M):
    L = int(round(math.sqrt(M)))
    return list(range(-(L - 1), L, 2))


def amp(M):
    return math.sqrt(3.0 / (2.0 * (M - 1)))                              # unit-energy scale of the integer levels


def nbits(M):
    return int(round(math.log2(math.sqrt(M))))


def level_bits_table(M, device='cpu'):
    """(L, nb) Gray bits (MSB first) of the ascending levels: index k -> k ^ (k >> 1). Equals mimo.GRAY for M = 4, 16;
    commpy's QAMModem (Gray-reordered snake) is the same per-dimension Gray code with the real part as the MSB group."""
    L, nb = len(levels(M)), nbits(M)
    g = [k ^ (k >> 1) for k in range(L)]
    return torch.tensor([[(gk >> (nb - 1 - j)) & 1 for j in range(nb)] for gk in g], dtype=torch.int8, device=device)


def to_bits(l, M):
    """Integer levels (..., D) -> Gray bits (..., D * nb)."""
    lv = levels(M)
    idx = ((l + (len(lv) - 1)) / 2).round().long().clamp(0, len(lv) - 1)
    return level_bits_table(M, l.device)[idx].flatten(-2)


def slice_levels(z, M):
    """Nearest constellation level per real dimension (ties to the lower level), clipped to the range."""
    lv = levels(M)
    k = torch.floor((z + (len(lv) - 1)) / 2 + 0.5)                      # nearest odd integer, x.5 rounds up
    tie = ((z + (len(lv) - 1)) / 2 - torch.floor((z + (len(lv) - 1)) / 2)) == 0.5
    k = torch.where(tie, k - 1, k)
    return (2 * k.clamp(0, len(lv) - 1) - (len(lv) - 1)).to(z.dtype)


def bit_errors(l_true, l_hat, M):
    bt, bh = to_bits(l_true, M), to_bits(l_hat, M)
    return int((bt != bh).sum()), bt.numel()


# ---------------------------------------------------------------- their channel model (App. 15, def_MIMO.create_instance)
def make_batch_pimi(B, Nt, Nr, M, ebn0_db, gen, device='cuda'):
    """Their generator in our conventions (mimo.make_batch's dict): H = a H_r, y = a y_r with H_r, y_r the real lift of
    their unnormalised model, so y = H l + n with integer levels l; N0 per instance (B,) = a^2 noise_power.
    noise_power = mean_i |(H~ x~)_i|^2 / (b Eb/N0), complex noise CN(0, noise_power)."""
    lv = torch.tensor(levels(M), device=device, dtype=torch.float32)
    idx = torch.randint(0, len(lv), (B, 2 * Nt), generator=gen, device=device)
    l = lv[idx]
    Hc = torch.complex(torch.randn(B, Nr, Nt, generator=gen, device=device),
                       torch.randn(B, Nr, Nt, generator=gen, device=device)) / math.sqrt(2)
    xc = torch.complex(l[:, :Nt], l[:, Nt:])
    yrec = torch.einsum('bij,bj->bi', Hc, xc)
    ey2 = (yrec.abs() ** 2).mean(-1)                                      # (B,)
    npow = ey2 / (10 ** (ebn0_db / 10) * math.log2(M))
    n = torch.complex(torch.randn(B, Nr, generator=gen, device=device),
                      torch.randn(B, Nr, generator=gen, device=device)) * torch.sqrt(npow / 2)[:, None]
    yc = yrec + n
    a = amp(M)
    H = mimo.complex_to_real(Hc) * a
    y = torch.cat([yc.real, yc.imag], -1) * a
    return dict(H=H, y=y, l=l, N0=(a * a) * npow, M=M, Nt=Nt, Nr=Nr, ebn0=ebn0_db)


def ebn0_to_snr(ebn0_db, M):
    """Our SNR (Nt Es / N0 per receive antenna, Es = 1; mimo.make_batch) of their Eb/N0: SNR = Eb/N0 + 10 log10(b),
    b = log2 M; theirs normalises each instance to its own received power, ours uses the expected power."""
    return ebn0_db + 10 * math.log10(math.log2(M))


def mmse_z(b):
    """Their MMSE filter (H^H H + noise_power / Es I)^-1 H^H y, in our units: the real-valued (G + (N0/2)/E[l^2] I)^-1 H^T y,
    i.e. mimo.mmse with N0 per instance or scalar; returns z in level units (biased, no z / mu correction)."""
    H, y, M = b['H'], b['y'], b['M']
    el2 = float(np.mean(np.square(levels(M))))
    G = H.transpose(1, 2) @ H
    D = G.shape[-1]
    N0 = b['N0']
    reg = (N0 / 2 / el2) if not torch.is_tensor(N0) else (N0 / 2 / el2)[:, None, None]
    A = G + reg * torch.eye(D, device=H.device)
    return torch.linalg.solve(A, torch.einsum('bij,bi->bj', H, y))


def problem(b, xm):
    """DI-MIMO couplings around integer levels xm (mimo.ising_delta_at, K = 1): float J (symmetrised), h = h0 / 2, and the
    fixed-point integers Jq, hq = q(J), q(h) (int32 tensors holding int16 values)."""
    I = mimo.ising_delta_at(b, xm, K=1)
    J = (I['J'] + I['J'].transpose(1, 2)) / 2
    h = I['h0'] / 2
    return quantize(J, h, xm)


def quantize(J, h, xm):
    Jq = torch.clamp(torch.trunc(J.double() * ONE), QMIN, QMAX).to(torch.int32)
    hq = torch.clamp(torch.trunc(h.double() * ONE), QMIN, QMAX).to(torch.int32)
    return dict(Jq=Jq.contiguous(), hq=hq.contiguous(), xm=xm)


def schedule(steps, beta=BETA, gamma=GAMMA):
    """(beta_int, eta_int list): q(beta), q(eta_t) with eta_t = sqrt(1 / (5 linspace(gamma0, gamma1, steps)))."""
    eta = np.sqrt(1.0 / (5.0 * np.linspace(gamma[0], gamma[1], steps)))
    q = lambda v: int(np.clip(np.trunc(v * ONE), QMIN, QMAX))
    return q(beta), [q(e) for e in eta]


# ---------------------------------------------------------------- the update (integer units, int64 tensors)
def _clip(x):
    return torch.clamp(x, QMIN, QMAX)


def _tdiv(x, d=ONE):
    return torch.div(x, d, rounding_mode='trunc')


def lut(si):
    return torch.where(si <= -2048, LUT_INT[0], torch.where(si <= 0, LUT_INT[1], torch.where(si <= 2048, LUT_INT[2],
                                                                                             LUT_INT[3])))


def step(s, field, hq, beta_int, eta_int, rv):
    """One synchronous PIMI step. s (B, R, N) int64 in {-1, 0, 1}; field = J s (exact integer); rv = q(N(0,1)) ints."""
    mvm = _clip(field)
    I = _clip(_tdiv(beta_int * (mvm + hq[:, None, :])))
    si = _clip(2 * I)
    L = lut(si)
    n = _clip(_tdiv(eta_int * rv))
    tot = _clip(L + ONE * s + n)
    return torch.sign(tot)


def jfield(Jf, s):
    """J s for integer J (as float32, |J| <= 2^15) and s in {-1, 0, 1}: exact in fp32 while |J s| < 2^24 (N <= 256 at
    |J| <= 2^12... the DI couplings are <= 2^12 in magnitude); TF32 must be off."""
    return torch.bmm(s.to(torch.float32), Jf.transpose(1, 2)).round().to(torch.int64)


def energy2(Jf, hq, s):
    """2 E = -s^T J s - 2 h^T s (integers), per trial."""
    Js = jfield(Jf, s)
    return -(s * (Js + 2 * hq[:, None, :])).sum(-1)


@torch.no_grad()
def run(P, steps, trials, noise, init, beta=BETA, gamma=GAMMA):
    """Generic driver. noise(k) -> rv (B, R, N) int64 for step k; init -> s0 (B, R, N) int64. Returns final spins
    (B, R, N) int64 and 2E (B, R) int64."""
    Jf = P['Jq'].to(torch.float32)
    hq = P['hq'].to(torch.int64)
    beta_int, eta = schedule(steps, beta, gamma)
    s = init
    for k in range(steps):
        s = step(s, jfield(Jf, s), hq, beta_int, eta[k], noise(k))
    return s, energy2(Jf, hq, s)


def pimi_torch(P, steps, trials=TRIALS, gen=None, beta=BETA, gamma=GAMMA):
    B, N = P['hq'].shape
    dev = P['hq'].device
    s0 = (torch.randint(0, 2, (B, trials, N), generator=gen, device=dev) * 2 - 1).to(torch.int64)
    noise = lambda k: torch.clamp(torch.trunc(torch.randn(B, trials, N, generator=gen, device=dev) * ONE), QMIN,
                                  QMAX).to(torch.int64)
    return run(P, steps, trials, noise, s0, beta, gamma)


def pimi_inject(P, steps, rv_float, s0, beta=BETA, gamma=GAMMA):
    """rv_float (steps, B, R, N) float64 N(0,1) samples, s0 (B, R, N) +-1: q(rv) exactly as the authors' quant_rv."""
    rq = torch.clamp(torch.trunc(rv_float * ONE), QMIN, QMAX).to(torch.int64)
    return run(P, steps, s0.shape[1], lambda k: rq[k], s0.to(torch.int64), beta, gamma)


# ---------------------------------------------------------------- Philox + inverse-CDF noise (kernel definition)
_TABLE = {}


def gauss_table(device='cpu'):
    """T[k] = q(Phi^-1((k + 1/2) / 2^16)), k = 0..2^16 - 1 (int16 values; tails cut at +-4.33 sigma)."""
    key = str(device)
    if key not in _TABLE:
        k = torch.arange(1 << 16, dtype=torch.float64)
        x = torch.special.ndtri((k + 0.5) / 65536.0)
        _TABLE[key] = torch.clamp(torch.trunc(x * ONE), QMIN, QMAX).to(torch.int32).to(device).contiguous()
    return _TABLE[key]


def philox_words(n, B, R, N, seed, inst0, dev):
    k0, k1 = seed & anefx.MASK, (seed >> 32) & anefx.MASK
    i = torch.arange(N, device=dev, dtype=torch.int64)[None, None, :]
    r = torch.arange(R, device=dev, dtype=torch.int64)[None, :, None]
    m = (inst0 + torch.arange(B, device=dev, dtype=torch.int64))[:, None, None]
    return anefx.philox(torch.full_like(i, n), i, r, m, k0, k1)


def pimi_fx(P, steps, trials, seed, inst0=0, beta=BETA, gamma=GAMMA):
    """Bit-exact definition of the kernel: start spin +1 iff word 0 of counter (2^32 - 1, i, r, m) >= 2^31; step k uses
    word k mod 4 of counter (k // 4, i, r, m), its top 16 bits indexing gauss_table."""
    B, N = P['hq'].shape
    dev = P['hq'].device
    tab = gauss_table(dev).to(torch.int64)
    x0 = philox_words(anefx.MASK, B, trials, N, seed, inst0, dev)[0]
    s0 = torch.where(x0 >= 2 ** 31, 1, -1).to(torch.int64)
    cache = {}

    def noise(k):
        if k // 4 not in cache:
            cache.clear()
            cache[k // 4] = philox_words(k // 4, B, trials, N, seed, inst0, dev)
        return tab[cache[k // 4][k % 4] >> 16]
    return run(P, steps, trials, noise, s0, beta, gamma)


# ---------------------------------------------------------------- decision
def select(P, S, E2):
    """First trial with the lowest final energy; returns its spins (B, N)."""
    im = E2.argmin(1)
    return S[torch.arange(S.shape[0], device=S.device), im]


def decide(P, s_best, M):
    """x = x_mmse + T s (T = [I, I]), sliced to the constellation."""
    D = P['xm'].shape[-1]
    d = (s_best[:, :D] + s_best[:, D:]).to(torch.float32)
    return slice_levels(P['xm'] + d, M)


def detect_torch(b, steps, trials=TRIALS, gen=None, z=None, sched=None):
    """The whole PIMI chain in PyTorch: their MMSE, DI mapping, fixed point, solver, selection, reconstruction."""
    M = b['M']
    beta, gamma = SCHED[sched] if sched else sched_for(b['Nt'], M)
    z = mmse_z(b) if z is None else z
    P = problem(b, slice_levels(z, M))
    S, E2 = pimi_torch(P, steps, trials, gen, beta=beta, gamma=gamma)
    return decide(P, select(P, S, E2), M)


# ---------------------------------------------------------------- CUDA kernel launcher
class PimiKernel(anefx.Kernel):
    MPLS = (1, 2, 3, 4, 6, 8)                                             # N / 32
    MAXW = {1: 32, 2: 32, 3: 8, 4: 8, 6: 8, 8: 8}                       # warps per block (__launch_bounds__)

    def __init__(self, cubin):
        super().__init__(cubin)
        self.tab = None

    def pimi(self, P, steps, trials, seed, inst0=0, mode='chains', warps=8, beta=BETA, gamma=GAMMA):
        """Same contract as pimi_fx: mode 'chains' -> final spins int8 (B, R, N), 2E int32 (B, R);
        mode 'best' -> the selected trial's spins (B, N) and its 2E (B,)."""
        Jq, hq = P['Jq'], P['hq']
        B, N = hq.shape
        mpl = N // 32
        assert N % 32 == 0 and mpl in self.MPLS, 'unsupported spin count %d' % N
        if self.tab is None:
            self.tab = gauss_table('cuda').to(torch.int16).contiguous()
        beta_int, eta = schedule(steps, beta, gamma)
        eta_t = torch.tensor(eta, dtype=torch.int32, device='cuda')
        J16 = Jq.to(torch.int16).contiguous()
        h32 = hq.to(torch.int32).contiguous()
        W = max(1, min(warps, trials, self.MAXW[mpl]))
        smem = ((N * N * 2 + 15) // 16) * 16 + 4 * (N + 2 * 32)
        if mode == 'best':
            out_s = torch.empty(B, N, dtype=torch.int8, device='cuda')
            out_e = torch.empty(B, dtype=torch.int32, device='cuda')
        else:
            out_s = torch.empty(B, trials, N, dtype=torch.int8, device='cuda')
            out_e = torch.empty(B, trials, dtype=torch.int32, device='cuda')
        self.launch('pimi_m%d' % mpl, B, 32 * W, smem,
                    [J16, h32, eta_t, self.tab, beta_int, steps, trials, N, ('u32', seed & anefx.MASK),
                     ('u32', (seed >> 32) & anefx.MASK), inst0, 1 if mode == 'best' else 0, out_s, out_e])
        return out_s, out_e


def detect_kernel(b, kern, steps, trials, seed, z=None, inst0=0, sched=None, warps=8):
    """The PIMI chain with the CUDA kernel as the solver (preprocessing and reconstruction in PyTorch)."""
    M = b['M']
    beta, gamma = SCHED[sched] if sched else sched_for(b['Nt'], M)
    z = mmse_z(b) if z is None else z
    P = problem(b, slice_levels(z, M))
    s8, _ = kern.pimi(P, steps, trials, seed, inst0=inst0, mode='best', warps=warps, beta=beta, gamma=gamma)
    return decide(P, s8.to(torch.int64), M)
