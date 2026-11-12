#!/usr/bin/env python3
"""Prediction table for PROTOCOL_B.md, from development timings only (written before the cohort):
- kernel items: the idle-GPU3 development profile (results/kernel_tests/prof_v2_gpu3_dev.log) where it has the
  configuration and anneal count (16x16 QPSK RI, 16x16 16-QAM dDI; 16x16 QPSK DI is predicted from the 16-QAM dDI
  numbers, same spin count, phases and steps); the massive shape from its scaling-sweep timing on the shared GPU6;
  range = development value x [0.6, 1.6];
- scaling items: the sweeps' development times per detection (shared GPU6 / shared CPU): GPU range x [1/5, 1.5] of
  the dev time per detection, CPU range x [1/3, 2];
- power under load 400-1000 W; J per detection = power / rate, at the range ends.
Usage: predict_b.py PLAN_B.json SCALE_SUMMARY.json > predictions.md"""
import json
import re
import sys

plan = json.load(open(sys.argv[1]))
summ = json.load(open(sys.argv[2]))
dev = {}
for l in open('../results/kernel_tests/prof_v2_gpu3_dev.log'):
    m = re.match(r'(\w+) R(\d+)\s+per-stage us/det: mmse ([\d.]+) map ([\d.]+) fixed ([\d.]+) kernel ([\d.]+) select ([\d.]+)', l)
    if m:
        name, R = m.group(1), int(m.group(2))
        mm, mp, fx, k, sel = (float(m.group(i)) for i in range(3, 8))
        dev[(name, R)] = dict(mmse=mm, kernel=k, e2e=mm + mp + fx + k + sel)
alias = {'q16_ri': 'q16', 'x16_ddi': 'x16', 'q16_di': 'x16'}
P_LO, P_HI = 400.0, 1000.0


def rng(us_lo, us_hi):
    r_hi, r_lo = 1 / us_lo, 1 / us_hi                                     # M det/s
    return r_lo, r_hi, P_LO / (r_hi * 1e6) * 1e3, P_HI / (r_lo * 1e6) * 1e3


print('| Item | detections/s (M) | J per detection, total (mJ) | meets 8.4 M/s |')
print('|---|---|---|---|')
for g in plan['gpu']:
    tag = '%s %s%s' % (g['name'], g['mode'], (' R%d' % g['R']) if g.get('R') else '')
    us = None
    if g.get('scaling'):
        k = g['name'][len('scale_'):]
        s = summ[k]
        us = s['dev_us_R']
        lo, hi = us / 5, us * 1.5
    else:
        a = alias.get(g['name'])
        if a and g['mode'] == 'mmse':
            us = dev[(a, 4)]['mmse']
        elif a and (a, g['R']) in dev:
            us = dev[(a, g['R'])][g['mode']]
        elif a and g['R'] == 1:
            us = dev[(a, 4)][g['mode']] / 3.5
        if us is None:                                                    # massive shape: its sweep timing
            k = plan['massive']['config']
            s = summ[k]
            us = s['dev_us_R'] * g.get('R', 1) / s['R'] if g['mode'] != 'mmse' else 0.15
            lo, hi = us / 5, us * 1.5
        else:
            lo, hi = us / 1.6, us / 0.6
    r_lo, r_hi, j_lo, j_hi = rng(lo, hi)
    meets = 'yes' if r_lo >= 8.4 else ('no' if r_hi < 8.4 else 'uncertain')
    print('| %s | %.3g–%.3g | %.3g–%.3g | %s |' % (tag, r_lo, r_hi, j_lo, j_hi, meets))
print('\n| CPU item (K-best, all threads) | K | µs per detection |')
print('|---|---|---|')
for c in plan['cpu']:
    s = summ[c['name'][len('scale_'):]]
    print('| %s | %d | %.3g–%.3g |' % (c['name'], c['K'], s['dev_us_K'] / 3, s['dev_us_K'] * 2))
