#!/usr/bin/env python3
"""A5.5 kernels (PROTOCOL_A55.md). New code only; apx.py, runner.py and mimo.py are not edited.
fa_seq: first-accept sequential update. One pass tests every lane of one copy bank against the current fields, commits the
first accepted lane in scan order, re-tests the lanes after it, and so on. With one random number per spin per sweep this is the
index-order sequential update of apx.sa_seq (test_a55.py requires bit identity). rule 'm': Metropolis; rule 'r': rule (2).
ape_k: mimo.anechoic at kappa = 0 with a start option and a flip counter. pt_k: apx.snowball_par with a start option.
Start 'rand': as now. Start 'bal': each coordinate gets P/2 copies +1 and P/2 -1, uniform and independent per coordinate and
anneal, so d = 0 and the first candidate is the guess x_g."""
import math

import torch

import apx

mimo = apx.mimo
ARMS = ('abl_fam_', 'abl_far_', 'abl_ape_', 'abl_ptb_')


def start_spins(B, R, N, P, st, gen, dev):
    if st == 'rand':
        return torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    if st == 'bal':
        rk = torch.rand(B, R, P, N // P, generator=gen, device=dev).argsort(2).argsort(2)
        return torch.where(rk < P // 2, 1.0, -1.0).reshape(B, R, N)
    raise ValueError(st)


@torch.no_grad()
def fa_seq(I, R, S, T0, T1, K, rule='m', q=0.0, start='rand', gen=None, count=None):
    """Returns best_s (B, R, N). count: per K, flips, tests (comparator passes), last (flips on a pass's last lane), decisions
    (S N per anneal), anneals, N. The model F cost per anneal is (tests + flips) / anneals; tests = S P anneals + flips - last."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    P = 2 * K
    D = N // P
    A = B * R
    s = start_spins(B, R, N, P, start, gen, dev)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = mimo.energy0(s, h0, J)
    s, u, E = s.reshape(A, N).clone(), u.reshape(A, N).clone(), E.reshape(A).clone()
    best_s, best_e = s.clone(), E.clone()
    Ts = mimo.geom(T0, T1, S, dev).tolist()
    Jt = J.transpose(1, 2).contiguous()
    bi = torch.arange(B, device=dev).repeat_interleave(R)
    lanes = torch.arange(D, device=dev)[None, :]
    metro = rule == 'm'
    nfl = ntests = nlast = 0
    for sw in range(S):
        T = Ts[sw]
        rnd = torch.rand(B, R, N, generator=gen, device=dev).reshape(A, N)
        for p in range(P):
            lo = p * D
            sb, ub, rb = s[:, lo:lo + D], u[:, lo:lo + D], rnd[:, lo:lo + D]
            ai, ptr = None, None
            while True:
                if ai is None:
                    ss, uu, rr, n = sb, ub, rb, A
                else:
                    ss, uu, rr, n = sb[ai], ub[ai], rb[ai], int(ai.numel())
                dE = 2 * ss * uu
                if metro:
                    acc = (dE <= 0) | (rr < torch.exp(-dE / T))
                else:
                    acc = (ss * uu + q) < ((rr - 0.5) * 4 * T)
                if ptr is not None:
                    acc = acc & (lanes >= ptr[:, None])
                ntests += n
                has = acc.any(1)
                nh = int(has.sum())
                if nh == 0:
                    break
                first = acc[has].float().argmax(1)
                aj = torch.nonzero(has).flatten() if ai is None else ai[has]
                g = lo + first
                si = s[aj, g]
                de = dE[has, first]
                delta = -2 * si
                u[aj] += 2 * delta[:, None] * Jt[bi[aj], g]
                s[aj, g] = si + delta
                E[aj] += de
                nfl += nh
                nxt = first + 1
                keep = nxt < D
                nlast += nh - int(keep.sum())
                ai, ptr = aj[keep], nxt[keep]
                if ai.numel() == 0:
                    break
            better = E < best_e
            best_e = torch.where(better, E, best_e)
            best_s = torch.where(better[:, None], s, best_s)
    if count is not None:
        d = count.setdefault(K, dict(flips=0.0, tests=0, last=0, decisions=0, anneals=0, N=N))
        d['flips'] += float(nfl)
        d['tests'] += ntests
        d['last'] += nlast
        d['decisions'] += A * N * S
        d['anneals'] += A
    return best_s.reshape(B, R, N)


@torch.no_grad()
def ape_k(I, R, S, t0, t1, q, P, start='rand', gen=None, count=None):
    """mimo.anechoic(I, R, S, t0, t1, q, kappa=0, phases=P) with a start option and a flip counter; same random-number order."""
    h, J = I['h'], I['J']
    B, N = h.shape
    dev = h.device
    T = mimo.geom(t0, t1, S, dev)
    s = start_spins(B, R, N, P, start, gen, dev)
    best_s, best_e = s.clone(), torch.full((B, R), float('inf'), device=dev)
    idx = torch.arange(N, device=dev) // (N // P)
    nfl = 0.0
    for k in range(S):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        z = s * u + q
        rr = (torch.rand(B, R, N, generator=gen, device=dev) - 0.5) * 4 * T[k]
        flip = (z < rr) & (idx == (k % P))
        if count is not None:
            nfl += float(flip.sum())
        s = torch.where(flip, -s, s)
        e = mimo.energy0(s, I['h0'], J)
        better = e < best_e
        best_e = torch.where(better, e, best_e)
        best_s = torch.where(better[..., None], s, best_s)
    if count is not None:
        d = count.setdefault(P // 2, dict(flips=0.0, steps=0, anneals=0, N=N))
        d['flips'] += nfl
        d['steps'] += S * B * R
        d['anneals'] += B * R
    return best_s


@torch.no_grad()
def pt_k(I, R, iters, T0, T1, P, start='rand', gen=None):
    """apx.snowball_par with a start option; the same statements in the same order otherwise."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    s = start_spins(B, R, N, P, start, gen, dev)
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
        ridx = torch.randint(0, N, (B, R, 1), generator=gen, device=dev)
        racc = torch.rand(B, R, 1, generator=gen, device=dev) < p.gather(-1, ridx)
        idx = torch.where(ok, idx, ridx)
        do = ok | racc
        si = s.gather(-1, idx)
        dEi = dE.gather(-1, idx)
        delta = torch.where(do, -2 * si, torch.zeros_like(si))
        s.scatter_(-1, idx, si + delta)
        u = u + 2 * delta * J[bi, idx[..., 0]]
        E = E + torch.where(do, dEi, torch.zeros_like(dEi))[..., 0]
        better = E < best_e
        best_e = torch.where(better, E, best_e)
        best_s = torch.where(better[..., None], s, best_s)
    return best_s


def solver_for(method, shape, gs, ctx, sink):
    """abl_fam_<S>_<T0>_<T1>_<st>_<Ns>, abl_far_<S>_<T0>_<T1>_<q>_<st>_<Ns>, abl_ape_<T0>_<T1>_<q>_<st>_<Ns>,
    abl_ptb_<cyc|fl>_<T0>_<T1>_<Ns>. Returns None for any other method."""
    if not method.startswith(ARMS):
        return None
    a = method.split('_')
    arm, Ns = a[1], int(a[-1])
    cnt = {}
    sink['cnt'] = cnt
    if arm == 'fam':
        S, T0, T1, st = int(a[2]), float(a[3]), float(a[4]), a[5]
        return (lambda I, na, K: fa_seq(I, na, S, T0, T1, K, rule='m', start=st, gen=gs, count=cnt)), None, Ns
    if arm == 'far':
        S, T0, T1, q, st = int(a[2]), float(a[3]), float(a[4]), float(a[5]), a[6]
        return (lambda I, na, K: fa_seq(I, na, S, T0, T1, K, rule='r', q=q, start=st, gen=gs, count=cnt)), None, Ns
    if arm == 'ape':
        T0, T1, q, st = float(a[2]), float(a[3]), float(a[4]), a[5]
        return (lambda I, na, K: ape_k(I, na, apx.MA['Sk'] * 2 * K, T0, T1, q, 2 * K, start=st, gen=gs, count=cnt)), None, Ns
    bud, T0, T1 = a[2], float(a[3]), float(a[4])
    phi = ctx.tuned['flip_phi'][shape]

    def nit(K, N):                                                         # A5's budgets (a) cyc and (b) fl, as apx.mdi_solver_for
        L = apx.MA['Sk'] * 2 * K
        F = phi[str(K)] * L
        if bud == 'fl':
            return max(1, int(round(F)))
        return max(1, int(round((L + F) / (1 + math.ceil(math.log2(N))))))
    return (lambda I, na, K: pt_k(I, na, nit(K, I['h'].shape[1]), T0, T1, 2 * K, start='bal', gen=gs)), None, Ns
