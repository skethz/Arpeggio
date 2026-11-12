#!/usr/bin/env python3
"""A5.2 (exploratory, coordinator's go Sun 25 Oct 07:3x CET; PROTOCOL_A52.md): the parallel-trial tuning grid extended
below its corner (T0 in {0.075, 0.15} x T1 in {0.0125, 0.025, 0.05}) for BOTH budgets at P1-P3 on seed 1000; picks over
the union with the frozen 12 cells; held-out seed-102 re-runs of every pick (P1 pick reused at P2/P3 = the kill-arm
privilege; and per-point picks). Usage: make_plan_a52.py OUT.json"""
import json, sys
PT = {'P1': ('x16', 20.0, 32, 8000, 2000, 4000), 'P2': ('x32', 22.0, 8, 4000, 1000, 2000), 'P3': ('q32', 14.0, 8, 8000, 4000, 4000)}
J = []
for pt, (sh, snr, Ns, nmin, B, nt) in PT.items():
    bpu = 128 if sh == 'x32' else 64
    for bud in ('cyc', 'fl'):
        for T0 in (0.075, 0.15):
            for T1 in (0.0125, 0.025, 0.05):
                J.append(dict(set='tune', shape=sh, method='abl_ptt_%s_%g_%g_%d' % (bud, T0, T1, Ns), snr=snr, seed=1000, batch=B,
                              min_vec=0, min_bit=0, min_uses=nt, max_bits=nt * bpu, pri=-5, a52=True, needs_tuned='flip_phi'))
        J.append(dict(set='abl', shape=sh, method='abl_pt2%s_%d' % (bud[0], Ns), snr=snr, seed=102, batch=B, min_uses=nmin, point=pt,
                      pri=0, a52=True, needs_tuned='pt2_' + bud))
        if pt != 'P1':
            J.append(dict(set='abl', shape=sh, method='abl_pt2%sp_%d' % (bud[0], Ns), snr=snr, seed=102, batch=B, min_uses=nmin,
                          point=pt, pri=0, a52=True, needs_tuned='pt2_%s_%s' % (bud, sh)))
json.dump(dict(host='hostB', amendment='A5.2 exploratory', tuned_file='<SCRATCH>/ap_ber_20261024/results/tuned_a52.json',
               jobs=J), open(sys.argv[1], 'w'), indent=0)
print(len(J), 'jobs')
