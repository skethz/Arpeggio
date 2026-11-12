"""Antiphase engine: algorithmic reference (DESIGN.md §1-3). Vectorised over instances and anneals, int64 on CPU.

Inputs per sub-problem batch: G (B, D, D) int (dDI coupling block, symmetric, with diagonal), h (B, D) int, P copies,
schedule T (S,), c (S,) ints, q int, R anneals, 64-bit seed, inst0. Output: best spins (B, R, P*D) int8 in copy-major
order (spin p*D + j), best energy relative to the anneal's start state (B, R) int64, flips per step (S,) summed.

rng='philox': anefx's Philox4x32-10 streams (RB = 32) -> equals anefx.anechoic_fx (mode 'chains') with
              best_e - e0 = Δbest.
rng='xs':     production streams: per (anneal, lane) xorshift32 seeded by fmix32 (RB = 16).
"""
import torch

MASK = 0xFFFFFFFF
PHI = 0x9E3779B9


def _mul32(a, m):
    """(a * m) mod 2^32 for int64 tensors holding uint32 values (m an int constant)."""
    a_lo, a_hi = a & 0xFFFF, a >> 16
    m_lo, m_hi = m & 0xFFFF, m >> 16
    return (a_lo * m_lo + (((a_lo * m_hi + a_hi * m_lo) & 0xFFFF) << 16)) & MASK


def fmix32(h):
    h = h ^ (h >> 16)
    h = _mul32(h, 0x85EBCA6B)
    h = h ^ (h >> 13)
    h = _mul32(h, 0xC2B2AE35)
    return h ^ (h >> 16)


def xs32(x):
    x = x ^ ((x << 13) & MASK)
    x = x ^ (x >> 17)
    return x ^ ((x << 5) & MASK)


def lane_seeds(seed, inst, r, D):
    """inst (B,1,1) and r (1,R,1) int64 tensors -> lane states (B, R, D) (nonzero)."""
    lo, hi = seed & MASK, (seed >> 32) & MASK
    b = fmix32(fmix32(fmix32(lo ^ inst) ^ hi) ^ r)
    j = torch.arange(1, D + 1, dtype=torch.int64)[None, None, :]
    st = fmix32((b + j * PHI) & MASK)
    return torch.where(st == 0, torch.full_like(st, PHI), st)


def compress(F, K):
    """anefx.to_fixed output (dDI, 2K copies) -> G (B, D, D), h (B, D) int64; asserts the replicated structure."""
    Ji = F['J'].long()
    B, N = F['h'].shape
    D = N // (2 * K)
    G = -Ji[:, :D, D:2 * D]
    E = -G.repeat(1, 2 * K, 2 * K)
    E[:, torch.arange(N), torch.arange(N)] = 0
    assert bool((E == Ji).all()), 'coupling matrix is not the dDI replication'
    h = F['h'].long()[:, :D]
    assert bool((F['h'].long().reshape(B, 2 * K, D) == h[:, None]).all())
    assert bool((F['h'] == F['h0']).all())
    return G.contiguous(), h.contiguous()


def expand(G, h, K):
    """Inverse of compress: (J int16 (B, N, N), h int32 (B, N)) as anefx expects."""
    B, D, _ = G.shape
    N = 2 * K * D
    J = -G.repeat(1, 2 * K, 2 * K)
    J[:, torch.arange(N), torch.arange(N)] = 0
    hh = h.repeat(1, 2 * K)
    return J.to(torch.int16), hh.to(torch.int32)


@torch.no_grad()
def antiphase_ref(G, h, P, T, c, q, R, seed, inst0=0, rng='xs'):
    import anefx
    G = G.long(); h = h.long()
    B, D, _ = G.shape
    S = len(T)
    T = [int(v) for v in T]; c = [int(v) for v in c]
    Gd = G.double()
    diag = torch.diagonal(G, dim1=1, dim2=2)[:, None, :]              # (B, 1, D)
    inst = (inst0 + torch.arange(B, dtype=torch.int64))[:, None, None]
    r = torch.arange(R, dtype=torch.int64)[None, :, None]
    j = torch.arange(D, dtype=torch.int64)[None, None, :]
    k0, k1 = seed & MASK, (seed >> 32) & MASK
    s = torch.empty(B, R, P, D, dtype=torch.int64)
    if rng == 'philox':
        RB = 32
        for p in range(P):
            x = anefx.philox(torch.full_like(j, MASK), p * D + j, r, inst, k0, k1)[0]
            s[:, :, p] = torch.where(x >= 2 ** 31, 1, -1)
    else:
        RB = 16
        x = xs32(lane_seeds(seed, inst, r, D))
        for p in range(P):
            s[:, :, p] = torch.where(((x >> (31 - p)) & 1) == 1, 1, -1)
    mv = lambda v: torch.einsum('bij,brj->bri', Gd, v.double()).round().long()   # exact (|values| < 2^53)
    m = s.sum(2)
    w = h[:, None, :] - 2 * mv(m)                                        # lane fields (B, R, D)
    de = torch.zeros(B, R, dtype=torch.int64)
    best = torch.full((B, R), 2 ** 62, dtype=torch.int64)
    best_s = s.clone()
    flips = torch.zeros(S, dtype=torch.int64)
    for k in range(S):
        p, n = k % P, k // P
        A, Bk = 4 * T[k], q - c[k] + 2 * T[k]
        if rng == 'philox':
            u = anefx.philox(torch.full_like(j, n >> 2), p * D + j, r, inst, k0, k1)[n & 3]
        else:
            x = xs32(x)
            u = x >> 16
        sp = s[:, :, p]
        zp = sp * w + 2 * diag + Bk
        F = u * A > zp * (1 << RB)
        sf = sp * F                                                       # s_old on flipped lanes, 0 elsewhere
        Gsf = mv(sf)
        de = de + (4 * sf * w).sum(-1) + 8 * (sf * Gsf).sum(-1)
        w = w + 4 * Gsf
        s[:, :, p] = torch.where(F, -sp, sp)
        flips[k] = int(F.sum())
        better = de < best
        best = torch.where(better, de, best)
        best_s = torch.where(better[..., None, None], s, best_s)
    return best_s.reshape(B, R, P * D).to(torch.int8), best, flips


def start_energy_anefx(F, R, seed, P, inst0=0):
    """2 E0 of anefx's start state (its formula e = sum s (h - 2 h0 - u)), for the Δ comparison."""
    import anefx
    MASKL = MASK
    J = F['J'].double(); hh, h0 = F['h'].long(), F['h0'].long()
    B, N = hh.shape
    k0, k1 = seed & MASKL, (seed >> 32) & MASKL
    i = torch.arange(N, dtype=torch.int64)[None, None, :]
    r = torch.arange(R, dtype=torch.int64)[None, :, None]
    m = (inst0 + torch.arange(B, dtype=torch.int64))[:, None, None]
    x = anefx.philox(torch.full_like(i, MASKL), i, r, m, k0, k1)[0]
    s = torch.where(x >= 2 ** 31, 1, -1).to(torch.int64)
    u = hh[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s.double()).round().long()
    return (s * ((hh - 2 * h0)[:, None, :] - u)).sum(-1)
