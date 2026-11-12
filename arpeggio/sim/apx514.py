#!/usr/bin/env python3
"""A5.14 kernel (PROTOCOL_A514.md): first-accept SA with commit width W (rule (2) only). New code; apx55.py is not edited.
One test cycle tests every remaining lane of one copy bank against the current fields. The first min(W, accepted) accepted lanes
in scan order are committed one after another, each a field-update cycle with its energy change taken from the fields at its
commit (so lanes after the first commit act on a stale test, as parallel flips do). The lanes after the last committed lane are
re-tested. W = 1 is Arpeggio (apx55.fa_seq rule 'r'); solver_for sends W = 1 to apx55.fa_seq itself, and fa_seq_w(force=True)
runs this code at W = 1 for the bit-identity gate. Random numbers: one per spin per sweep, drawn as apx55.fa_seq draws them.
Method name: abl_faw_<W>_<S>_<T0>_<T1>_<q>_<st>_<Ns>. Counters as apx55.fa_seq plus 'commits' (commit groups): per anneal,
tests = S P + commits - last and the model-F cost is tests + flips (the find-first-W pick is charged nothing)."""
import torch

import apx
import apx55

mimo = apx.mimo


@torch.no_grad()
def fa_seq_w(I, R, S, T0, T1, K, W, q=0.0, start='rand', gen=None, count=None, force=False, audit=None):
    if W == 1 and not force:
        return apx55.fa_seq(I, R, S, T0, T1, K, rule='r', q=q, start=start, gen=gen, count=count)
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    P = 2 * K
    D = N // P
    A = B * R
    s = apx55.start_spins(B, R, N, P, start, gen, dev)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = mimo.energy0(s, h0, J)
    s, u, E = s.reshape(A, N).clone(), u.reshape(A, N).clone(), E.reshape(A).clone()
    best_s, best_e = s.clone(), E.clone()
    Ts = mimo.geom(T0, T1, S, dev).tolist()
    Jt = J.transpose(1, 2).contiguous()
    bi = torch.arange(B, device=dev).repeat_interleave(R)
    lanes = torch.arange(D, device=dev)[None, :]
    nfl = ntests = nlast = ncom = 0
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
                acc = (ss * uu + q) < ((rr - 0.5) * 4 * T)
                if ptr is not None:
                    acc = acc & (lanes >= ptr[:, None])
                ntests += n
                has = acc.any(1)
                nh = int(has.sum())
                if nh == 0:
                    break
                ah = acc[has]
                aj = torch.nonzero(has).flatten() if ai is None else ai[has]
                rank = ah.long().cumsum(1)                                  # 1-based rank of each accepted lane in scan order
                last = torch.zeros(nh, dtype=torch.long, device=dev)
                for w in range(W):                                          # commit the w-th accepted lane, in order
                    selw = ah & (rank == w + 1)
                    hw = selw.any(1)
                    if not bool(hw.any()):
                        break
                    rows = torch.nonzero(hw).flatten()
                    pos = selw[rows].float().argmax(1)
                    ar = aj[rows]
                    g = lo + pos
                    si = s[ar, g]
                    de = 2 * si * u[ar, g]                                  # energy change from the fields at commit
                    delta = -2 * si
                    u[ar] += 2 * delta[:, None] * Jt[bi[ar], g]
                    s[ar, g] = si + delta
                    E[ar] += de
                    nfl += int(rows.numel())
                    last[rows] = pos
                ncom += nh
                nxt = last + 1
                keep = nxt < D
                nlast += nh - int(keep.sum())
                ai, ptr = aj[keep], nxt[keep]
                if ai.numel() == 0:
                    break
            better = E < best_e
            best_e = torch.where(better, E, best_e)
            best_s = torch.where(better[:, None], s, best_s)
    if audit is not None:                                                   # gate G3: tracked energy against a recomputation
        audit['max_dE'] = max(audit.get('max_dE', 0.0), float((E - mimo.energy0(s.reshape(B, R, N), h0, J).reshape(A)).abs().max()))
        audit['tests_identity'] = audit.get('tests_identity', True) and ntests == S * P * A + ncom - nlast
    if count is not None:
        d = count.setdefault(K, dict(flips=0.0, tests=0, last=0, decisions=0, anneals=0, N=N, commits=0))
        d['flips'] += float(nfl)
        d['tests'] += ntests
        d['last'] += nlast
        d['decisions'] += A * N * S
        d['anneals'] += A
        d['commits'] = d.get('commits', 0) + ncom
    return best_s.reshape(B, R, N)


def solver_for(method, shape, gs, ctx, sink):
    """abl_faw_<W>_<S>_<T0>_<T1>_<q>_<st>_<Ns>; None for any other method."""
    if not method.startswith('abl_faw_'):
        return None
    a = method.split('_')
    assert len(a) == 9, method
    W, S, T0, T1, q, st, Ns = int(a[2]), int(a[3]), float(a[4]), float(a[5]), float(a[6]), a[7], int(a[8])
    cnt = {}
    sink['cnt'] = cnt
    return (lambda I, na, K: fa_seq_w(I, na, S, T0, T1, K, W, q=q, start=st, gen=gs, count=cnt)), None, Ns


def install():
    """Route abl_faw_* through this module wherever apx55.solver_for is called (a56lib.solver_for, runner_a55)."""
    if getattr(apx55, '_a514', False):
        return
    orig = apx55.solver_for

    def sf(method, shape, gs, ctx, sink):
        r = solver_for(method, shape, gs, ctx, sink)
        return r if r is not None else orig(method, shape, gs, ctx, sink)
    apx55.solver_for = sf
    apx55.ARMS = apx55.ARMS + ('abl_faw_',)
    apx55._a514 = True
