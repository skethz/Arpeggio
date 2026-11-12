#!/usr/bin/env python3
"""A5.6 X5b (PROTOCOL_A56.md section 8): period-2 returns and returns per move for alternation, in-phase (copies in phase, activity 1/P),
dilution (each spin free to flip with probability 1/P) and lane-random, on the same sub-problems, start and definitions as src/mech_trace.py (seed 103,
16x16 16-QAM, 20 dB, around the wrong MMSE guess, K = 1, 2, at most 200 sub-problems, generator seed 7, S = 128 P, T 0.3, q 0.4). Also at the re-tuned
values q 0.8, T 0.5 of the in-phase control. 95% intervals: cluster bootstrap over sub-problems. Usage: mech_a56.py OUT.json"""
import json
import sys

import numpy as np
import torch

import apx
import mimo
import a56lib as L

torch.backends.cuda.matmul.allow_tf32 = False
OUT = sys.argv[1]
b = apx.draw(103, 20.0, 0, 2000, 16, 16)
z, _, _ = mimo.mmse(b)
lm = mimo.quantize_levels(z / mimo._mu(b, z), 16)
D = 32


@torch.no_grad()
def run(I, s0, S, T, q, P, mode, gen):
    h, J = I['h'], I['J']
    B, R, N = s0.shape
    s = s0.clone()
    states = [s.clone()]
    idx = torch.arange(N, device=s.device) // (N // P)
    cls = apx.colour_classes(N, P, 'dim', 0, s.device) if mode == 'in_phase' else None
    for k in range(S):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        rr = (torch.rand(B, R, N, generator=gen, device=s.device) - 0.5) * 4 * T
        flip = s * u + q < rr
        if mode == 'alternation':
            flip = flip & (idx == (k % P))
        elif mode == 'in_phase':
            m = torch.zeros(N, dtype=torch.bool, device=s.device); m[cls[k % P]] = True
            flip = flip & m
        elif mode == 'dilution':
            flip = flip & (torch.rand(B, R, N, generator=gen, device=s.device) < 1.0 / P)
        elif mode == 'lane':
            flip = flip & L.lane_mask(B, R, N // P, P, gen, s.device)
        s = torch.where(flip, -s, s)
        states.append(s.clone())
    return torch.stack(states, 0)


def boot(fn, n, B=2000):
    rng = np.random.default_rng(12345)
    v = [fn(rng.integers(0, n, n)) for _ in range(B)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


res = dict(seed=103, shape='x16', snr=20.0, cases={})
for K in (1, 2):
    P = 2 * K
    td = b['l'] - lm
    sel = (td.abs().amax(-1) > 0) & (td.abs().amax(-1) <= 2 * K)
    ix = torch.nonzero(sel).flatten()[:200]
    sb = mimo.subset(b, ix)
    Ik = mimo.ising_delta_at(sb, lm[ix], K)
    g0 = torch.Generator(device='cuda'); g0.manual_seed(1030 + K)
    s0 = torch.where(torch.rand(len(ix), 1, P * D, generator=g0, device='cuda') < 0.5, -1.0, 1.0)
    S = 128 * P
    case = dict(K=K, n_inst=len(ix), half_steps=S, arms={})
    for name, mode, q, T in (('alternation', 'alternation', 0.4, 0.3), ('in_phase', 'in_phase', 0.4, 0.3), ('dilution', 'dilution', 0.4, 0.3), ('lane', 'lane', 0.4, 0.3),
                             ('in_phase_tuned', 'in_phase', 0.8, 0.5), ('alternation_q0', 'alternation', 0.0, 0.3)):
        g = torch.Generator(device='cuda'); g.manual_seed(7)
        st = run(Ik, s0, S, T, q, P, mode, g)[:, :, 0]
        d = st.reshape(S + 1, len(ix), P, D).sum(2)
        p2 = ((d[2:] == d[:-2]) & (d[1:-1] != d[:-2])).float().mean((0, 2)).cpu().numpy()   # per sub-problem
        # In-phase moves a coordinate only every P half-steps, so a one-half-step return cannot occur by construction. Also on each coordinate's clock: lag P.
        p2P = ((d[2 * P:] == d[:-2 * P]) & (d[P:-P] != d[:-2 * P])).float().mean((0, 2)).cpu().numpy()
        fl = (st[1:] != st[:-1]).float().sum(-1).mean(0).cpu().numpy()                        # flips per half-step, per sub-problem
        fm = lambda i: float(p2[i].mean())
        per_move = lambda i: float(p2[i].mean() / max(fl[i].mean() / D, 1e-12))
        case['arms'][name] = dict(q=q, T=T, returns=float(p2.mean()), returns_ci=boot(fm, len(ix)), flips_per_halfstep=float(fl.mean()),
                                  returns_per_move=per_move(np.arange(len(ix))), returns_per_move_ci=boot(per_move, len(ix)),
                                  returns_lagP=float(p2P.mean()), returns_lagP_ci=boot(lambda i: float(p2P[i].mean()), len(ix)),
                                  returns_lagP_per_move=float(p2P.mean() / max(fl.mean() / D, 1e-12)))
        print('K', K, name, json.dumps(case['arms'][name]), flush=True)
    res['cases']['K%d' % K] = case
json.dump(res, open(OUT, 'w'), indent=1)
