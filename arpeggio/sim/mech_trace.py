#!/usr/bin/env python3
"""PROTOCOL.md 6(a): per-half-step traces of the Antiphase solver with and without copy alternation on real delta
sub-problems (seed 103, 16x16 16-QAM, 20 dB, around the MMSE guess, K = 1 and K = 2), from the same random start,
T 0.3, q 0.4 (and q 0 as plain synchronous SCA). Same update as mimo.anechoic (kappa 0, constant T); every state is
recorded. Writes OUT.json: example traces (d_m(t), energy) and population curves / summaries over the instances whose
MMSE guess is wrong but whose truth lies inside the K-box. Usage: mech_trace.py OUT.json"""
import json
import sys

import torch

import apx
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
OUT = sys.argv[1]
b = apx.draw(103, 20.0, 0, 2000, 16, 16)
z, _, _ = mimo.mmse(b)
lm = mimo.quantize_levels(z / mimo._mu(b, z), 16)
D = 32
res = dict(seed=103, snr=20.0, shape='x16', T=0.3, q=0.4, cases={})


@torch.no_grad()
def run(I, s0, S, T, q, phases, gen):
    """mimo.anechoic's update with the start state given and every state kept: returns S+1 states and energies."""
    h, J = I['h'], I['J']
    B, R, N = s0.shape
    s = s0.clone()
    states, en = [s.clone()], [mimo.energy0(s, I['h0'], J)]
    idx = torch.arange(N, device=s.device) // (N // phases) if phases > 1 else None
    for k in range(S):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        zz = s * u + q
        rr = (torch.rand(B, R, N, generator=gen, device=s.device) - 0.5) * 4 * T
        flip = zz < rr
        if phases > 1:
            flip = flip & (idx == (k % phases))
        s = torch.where(flip, -s, s)
        states.append(s.clone()); en.append(mimo.energy0(s, I['h0'], J))
    return torch.stack(states, 0), torch.stack(en, 0)                    # (S+1, B, R, N), (S+1, B, R)


for K in (1, 2):
    P = 2 * K
    I = mimo.ising_delta_at(b, lm, K)
    td = b['l'] - lm                                                       # truth's delta (levels; steps of 2)
    sel = (td.abs().amax(-1) > 0) & (td.abs().amax(-1) <= 2 * K)
    ix = torch.nonzero(sel).flatten()[:200]
    sb = mimo.subset(b, ix)
    Ik = mimo.ising_delta_at(sb, lm[ix], K)
    tdk = td[ix]
    # truth spins: d = sum of P copies; npos copies at +1
    npos = ((tdk + P) / 2).round().long()
    c = torch.arange(P, device=tdk.device)[:, None]
    sT = torch.where(c[None] < npos[:, None, :], 1.0, -1.0).reshape(len(ix), P * D)
    eT = mimo.energy0(sT[:, None, :], Ik['h0'], Ik['J'])[:, 0]
    g0 = torch.Generator(device='cuda'); g0.manual_seed(1030 + K)
    s0 = torch.where(torch.rand(len(ix), 1, P * D, generator=g0, device='cuda') < 0.5, -1.0, 1.0)
    S = 128 * P
    case = dict(K=K, n_inst=len(ix), half_steps=S, variants={})
    for name, ph, q in (('alternation', P, 0.4), ('no_alternation', 1, 0.4), ('no_alternation_q0', 1, 0.0), ('alternation_q0', P, 0.0)):
        g = torch.Generator(device='cuda'); g.manual_seed(7)
        st, en = run(Ik, s0, S, 0.3, q, ph, g)
        st, en = st[:, :, 0], en[:, :, 0]                                  # one anneal: (S+1, B, N), (S+1, B)
        d = st.reshape(S + 1, len(ix), P, D).sum(2)                        # (S+1, B, D)
        dd = d[1:] - d[:-1]
        over = (dd.abs() >= 4).float()                                     # >= 2 levels in one half-step
        p2 = ((d[2:] == d[:-2]) & (d[1:-1] != d[:-2])).float()             # period-2 return
        flips = (st[1:] != st[:-1]).float().sum(-1)                        # spins flipped per half-step
        gap = en - eT[None]                                                # energy above the truth's energy
        best = torch.cummin(en, 0).values - eT[None]
        dist = (d - tdk[None]).abs().sum(-1) / 2                           # L1 distance to truth in levels
        v = dict(q=q, phases=ph,
                 mean_gap=gap.mean(1).tolist(), mean_best_gap=best.mean(1).tolist(),
                 overshoot_frac=over.mean((1, 2)).tolist(), period2_frac=p2.mean((1, 2)).tolist(),
                 flips_per_halfstep=flips.mean(1).tolist(), mean_dist_levels=dist.mean(1).tolist(),
                 frac_reached_truth_energy=float((best[-1] <= 1e-6).float().mean()),
                 frac_halfsteps_with_overshoot_first50=float((over[:50].amax(-1) > 0).float().mean()),
                 frac_dims_period2_any=float((p2.amax(0) > 0).float().mean()),
                 final_best_gap_mean=float(best[-1].mean()))
        ex = []
        for e in range(3):
            ex.append(dict(inst=int(ix[e]), d=d[:, e].tolist(), energy=en[:, e].tolist(), e_truth=float(eT[e]),
                           e_guess=float(mimo.energy0(Ik['sP'][e:e + 1, None, :], Ik['h0'][e:e + 1], Ik['J'][e:e + 1])[0, 0]),
                           truth_d=tdk[e].tolist()))
        v['examples'] = ex
        case['variants'][name] = v
        print('K', K, name, 'reached truth energy %.3f, overshoot(first 50 half-steps) %.3f, period-2 dims %.3f, final gap %.3f' % (
            v['frac_reached_truth_energy'], v['frac_halfsteps_with_overshoot_first50'], v['frac_dims_period2_any'],
            v['final_best_gap_mean']), flush=True)
    res['cases']['K%d' % K] = case
json.dump(res, open(OUT, 'w'))
