#!/usr/bin/env python3
"""A5.12 (PROTOCOL_A512.md, frozen 7 Nov 2026 15:47:35 CET, sha256 5dab3ffd...): parallel trial at c in {5, 3, 2} cycles
per iteration, I = round((L + F)/c). Tuning: the 18-cell A5 + A5.2 grid at P1, seed 1000. Held-out: the P1 pick of each c at
P1-P3, seed 102, batch sizes as (i). Held-out jobs come first in the plan and wait for their pick. Usage: make_plan_a512.py OUT.json"""
import json, sys
B_ = '<SCRATCH>/ap_ber_20261024/a512'
CS = (5, 3, 2)
GRID = [(T0, T1) for T0 in (0.3, 0.6, 1.2, 2.4) for T1 in (0.05, 0.15, T0)] + \
       [(T0, T1) for T0 in (0.075, 0.15) for T1 in (0.0125, 0.025, 0.05)]
PT = {'P1': ('x16', 20.0, 32, 8000, 2000), 'P2': ('x32', 22.0, 8, 4000, 1000), 'P3': ('q32', 14.0, 8, 8000, 4000)}
J = []
for c in CS:
    for pt, (sh, snr, Ns, nmin, B) in PT.items():
        J.append(dict(set='abl', shape=sh, method='abl_pt12c%d_%d' % (c, Ns), snr=snr, seed=102, batch=B, min_uses=nmin,
                      point=pt, pri=0, a512=True, needs_tuned='pt12_c%d' % c))
for c in CS:
    for T0, T1 in GRID:
        J.append(dict(set='tune', shape='x16', method='abl_ptt_c%d_%g_%g_32' % (c, T0, T1), snr=20.0, seed=1000, batch=2000,
                      min_vec=0, min_bit=0, min_uses=4000, max_bits=4000 * 64, pri=-5, a512=True, needs_tuned='flip_phi'))
json.dump(dict(host='hostA', amendment='A5.12 exploratory',
               protocol_sha256='5dab3ffd927be94a9bd04f79f2783fe9d6c1c43fd83b4f467e27de29401076cc',
               tuned_file=B_ + '/results/tuned_a512.json', jobs=J), open(sys.argv[1], 'w'), indent=0)
print(len(J), 'jobs')
