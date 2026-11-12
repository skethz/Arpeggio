#!/usr/bin/env python3
"""Amendment A3 (exploratory, NOT pre-registered; STATUS.md, 24 Oct 21:30): per-point re-tuning of variant (x) (symbol-
level synchronous heat-bath, random +-1-level proposals) AND, symmetrically, of Antiphase (q, T) at P2 and P3 on the
tuning seed 1000, because the P1-tuned (x) setting failed at P2/P3 on held-out seed 102. Stage 1 = set 'xtune'.
Stage 2 (set 'xheld', seed 102, same draws as the frozen ablation) is added by select_xexp.py.
Usage: make_plan_xexp.py OUT.json"""
import json, sys
jobs = []
for pt, (sh, snr, batch, n) in {'P2': ('x32', 22.0, 1000, 4000), 'P3': ('q32', 14.0, 4000, 8000)}.items():
    bpu = 128 if sh == 'x32' else 64
    for T in (0.05, 0.1, 0.2, 0.4, 0.8):
        for q in (0.0, 0.2, 0.4):
            jobs.append(dict(set='xtune', shape=sh, method='abl_symt_prop_%g_%g_8' % (T, q), snr=snr, seed=1000, batch=batch,
                             min_vec=0, min_bit=0, min_uses=n, max_bits=n * bpu, point=pt, pri=0))
    for q in (0.2, 0.4, 0.8):
        for T in (0.1, 0.2, 0.3, 0.5):
            jobs.append(dict(set='xtune', shape=sh, method='abl_qt_a_%g_%g_8' % (q, T), snr=snr, seed=1000, batch=batch,
                             min_vec=0, min_bit=0, min_uses=n, max_bits=n * bpu, point=pt, pri=0))
jobs.sort(key=lambda j: (0 if j['shape'] == 'q32' else 1, j['method']))
json.dump(dict(host='hostB', amendment='A3 exploratory', jobs=jobs), open(sys.argv[1], 'w'), indent=0)
print(len(jobs), 'jobs')
