#!/usr/bin/env python3
"""A5.6 library (exploratory; PROTOCOL_A56.md). apx.py, runner.py and mimo.py are not edited.
- ape(): mimo.anechoic statement for statement (same random-number order, so bit-identical for sched='alt'), plus flip
  counts per K and the lane-random schedule of review item X4.
- mdi_trace(): apx.mdi_diag statement for statement, plus a checkpoint per use at the start and after every stage.
- stop_eval(): what any residual-test early stop would have done, from one trace.
Method names: a56_<Sk>_<T0>_<T1>_<q>_<kappa>_<sched>_<Ns>, sched in {alt, lane}, L = Sk * 2K half-steps."""
import hashlib
import math

import numpy as np
import torch

import apx
import apx55

mimo = apx.mimo


def mhash(m):
    return int(hashlib.sha256(m.encode()).hexdigest()[:8], 16) % 1_000_000


def lane_mask(B, R, D, P, gen, dev):
    """Exactly one active copy per coordinate and anneal, drawn independently at every half-step. Spins are copy-major:
    spin i is copy i // D of coordinate i % D. Returns a bool mask (B, R, P D)."""
    c = torch.randint(0, P, (B, R, D), generator=gen, device=dev)
    idx = torch.arange(P * D, device=dev) // D
    return idx == c.repeat(1, 1, P)


@torch.no_grad()
def ape(I, R, S, t0, t1, q, kappa=0.0, P=1, sched='alt', gen=None, cnt=None):
    """mimo.anechoic(I, R, S, t0, t1, q, kappa=kappa, gen=gen, phases=P), track='best', ramp=True. Returns the best state of
    each anneal. cnt: optional dict accumulating flips, half-steps (steps) and anneals."""
    h, J = I['h'], I['J']
    B, N = h.shape
    dev = h.device
    T = mimo.geom(t0, t1, S, dev)
    t = torch.arange(S, device=dev, dtype=torch.float32)
    rho = torch.where(t >= 0.7 * S, (S - 1 - t) / max(1.0, S - 1 - 0.7 * S), torch.ones_like(t))
    s = torch.where(torch.rand(B, R, N, generator=gen, device=dev) < 0.5, -1.0, 1.0)
    sprev = s.clone()
    best_s, best_e = s.clone(), torch.full((B, R), float('inf'), device=dev)
    D = N // P
    idx = torch.arange(N, device=dev) // D
    nfl = 0.0
    for k in range(S):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        if k == 0:
            c = torch.zeros(B, R, 1, device=dev)
        else:
            c = torch.full((B, R, 1), float(kappa) * float(T[k - 1]) * float(rho[k]), device=dev)
        z = s * (u - c * sprev) + q
        rr = (torch.rand(B, R, N, generator=gen, device=dev) - 0.5) * 4 * T[k]
        flip = z < rr
        if sched == 'lane':
            flip = flip & lane_mask(B, R, D, P, gen, dev)
        elif P > 1:
            flip = flip & (idx == (k % P))
        sprev = s
        s = torch.where(flip, -s, s)
        if cnt is not None:
            nfl += float(flip.sum())
        e = mimo.energy0(s, I['h0'], J)
        better = e < best_e
        best_e = torch.where(better, e, best_e)
        best_s = torch.where(better[..., None], s, best_s)
    if cnt is not None:
        cnt['flips'] = cnt.get('flips', 0.0) + nfl
        cnt['steps'] = cnt.get('steps', 0.0) + float(S * B * R)
        cnt['anneals'] = cnt.get('anneals', 0.0) + float(B * R)
    return best_s


def solver_for(method, shape, gs, ctx, cnt):
    """(solver(I, na, K), to_levels or None, Ns). a56_* methods count flips per K in cnt; others are apx's, unchanged."""
    if method.startswith('a56_'):
        _, Sk, T0, T1, q, ka, sched, Ns = method.split('_')
        Sk, T0, T1, q, ka, Ns = int(Sk), float(T0), float(T1), float(q), float(ka), int(Ns)

        def f(I, na, K):
            return ape(I, na, Sk * 2 * K, T0, T1, q, ka, 2 * K, sched, gs, cnt.setdefault(str(K), {}))
        return f, None, Ns
    r = apx55.solver_for(method, shape, gs, ctx, cnt)                      # abl_fam_*, abl_far_*, abl_ape_*, abl_ptb_*; counts in cnt['cnt']
    return r if r is not None else apx.mdi_solver_for(method, shape, gs, ctx)


@torch.no_grad()
def mdi_trace(b, solver, Ns, Rmax, S, guesses=('mmse', 'sic'), heuristic='mean', sic_per='real', na_round='ceil',
              z_mmse=None, to_levels=None):
    """apx.mdi_diag with omega None, statement for statement, so the output and the solver's random numbers are the same.
    Checkpoint j = 0 is the start, j = st + 1 follows stage st; each holds what the wrapper would return if it ended there:
    d (the better guess's ||y - Hx||^2), be (its bit errors). Also ann (B, S, Rmax): anneals per stage and K; rad (B, G, S):
    radius per guess and stage; win (B, G, S): the K whose candidate became the guess at that stage, 0 if the guess stayed."""
    M = b['M']
    B, D = b['H'].shape[0], b['H'].shape[-1]
    dev = b['H'].device
    tl = to_levels or mimo.spins_to_levels_delta
    if z_mmse is None:
        z_mmse, Ai, _ = mimo.mmse(b)
    cur = {}
    for g in guesses:
        cur[g] = mimo.quantize_levels(z_mmse / mimo._mu(b, z_mmse), M) if g == 'mmse' else mimo.mmse_sic(b, per=sic_per)
    G = len(guesses)
    ck_d = torch.zeros(B, S + 1, dtype=torch.float64)
    ck_be = torch.zeros(B, S + 1, dtype=torch.int32)
    ann = torch.zeros(B, S, Rmax, dtype=torch.int32, device=dev)
    rad = torch.zeros(B, G, S, dtype=torch.int8)
    win = torch.zeros(B, G, S, dtype=torch.int8, device=dev)
    bd64 = dict(H=b['H'].double(), y=b['y'].double())

    def checkpoint(j):
        allc = torch.stack([cur[g] for g in guesses], 1)
        d = mimo.dist(b, allc)
        lh = allc[torch.arange(B, device=dev), d.argmin(1)]
        ck_d[:, j] = apx.dist_of(bd64, lh.double()).cpu()
        ck_be[:, j] = apx.biterr_per_use(b, lh).cpu()

    checkpoint(0)
    for st in range(S):
        R = {g: apx.mdi_radius_om(b, cur[g], Rmax, heuristic, None)[0] for g in guesses}
        tot = sum(R[g] for g in guesses)
        for gi, g in enumerate(guesses):
            rad[:, gi, st] = R[g].to(torch.int8).cpu()
        if int(tot.max()) == 0:
            for j in range(st + 1, S + 1):
                ck_d[:, j] = ck_d[:, st]
                ck_be[:, j] = ck_be[:, st]
            break
        nxt = {}
        for gi, g in enumerate(guesses):
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
                    win[idx[better], gi, st] = K
                    ann[idx, st, K - 1] += na
            nxt[g] = bl
        cur = nxt
        checkpoint(st + 1)
    allc = torch.stack([cur[g] for g in guesses], 1)
    d = mimo.dist(b, allc)
    lh = allc[torch.arange(B, device=dev), d.argmin(1)]
    return lh, dict(d=ck_d.numpy(), be=ck_be.numpy(), ann=ann.cpu().numpy(), rad=rad.numpy(), win=win.cpu().numpy())


def threshold(Nr, c):
    """||y - Hx||^2 / N0 of the true x is Gamma(Nr, 1): mean Nr, standard deviation sqrt(Nr)."""
    return Nr + c * math.sqrt(Nr)


def stop_eval(t, be, ann, thr, cyc):
    """t = d / N0 (U, S+1); be (U, S+1); ann (U, S, Rmax); cyc[K-1] = modeled cycles per anneal at K. The first checkpoint with
    t <= thr ends the search; a use that never passes runs to the end. Returns per-use bit errors, cycles, and stop index."""
    U, J = t.shape
    S = J - 1
    hit = t <= thr
    first = np.where(hit.any(1), hit.argmax(1), S)
    a = np.arange(U)
    per_stage = (ann * np.asarray(cyc, dtype=np.float64)).sum(-1)
    C = np.concatenate([np.zeros((U, 1)), np.cumsum(per_stage, 1)], 1)
    return be[a, first], C[a, first], first
