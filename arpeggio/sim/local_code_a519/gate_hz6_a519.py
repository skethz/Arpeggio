#!/usr/bin/env python3
"""A5.19 host check HZ6. hostB GPU2 reruns hostA's S* calibration batch for S = 280 (P4, seed 1000,
batch index 50, 500 uses, `abl_far_280_0.1_0.1_0_bal_8`), the high-S Arpeggio path that A* uses and that the five batches of gate_hz_a519.py did not cover.
The job carries no 'saved' key (no bit-for-bit assertion); this script compares per-use bit errors and counters with hostA's file.
Pass: at most 0.5% of uses differ (as in gate_hz_a519.py).
Usage: gate_hz6_a519.py plan ROOT | compare ROOT REF.npz OUT.json"""
import json
import os
import sys

import numpy as np

M = 'abl_far_280_0.1_0.1_0_bal_8'
JOB = dict(set='hz6', shape='x64', method=M, snr=22.0, batch=500, point='P4', seed=1000, first_batch=50, n_batches=1)
mode, ROOT = sys.argv[1], sys.argv[2]
if mode == 'plan':
    os.makedirs(ROOT, exist_ok=True)
    json.dump(dict(jobs=[JOB]), open(os.path.join(ROOT, 'plan.json'), 'w'), indent=1)
    print('wrote 1 job')
    sys.exit(0)


def cnt(info):
    c = info.get('cnt') or {}
    return c.get('cnt', c) if isinstance(c, dict) else {}


REF, OUT = sys.argv[3], sys.argv[4]
a, b = np.load(os.path.join(ROOT, 'hz6', 'x64', M, 'snr_22.00', 'b00050.npz')), np.load(REF)
x, y = a['biterr'].astype(np.int64), b['biterr'].astype(np.int64)
ia, ib = json.loads(str(a['info'])), json.loads(str(b['info']))
ca, cb = cnt(ia), cnt(ib)
rel, cost = {}, {}
for K in sorted(set(ca) & set(cb)):
    for f in ('flips', 'tests', 'steps', 'anneals'):
        if f in ca[K] and f in cb[K] and float(cb[K][f]):
            rel['%s_%s' % (K, f)] = float(ca[K][f]) / float(cb[K][f]) - 1
    pa = (float(ca[K].get('tests', ca[K].get('steps', 0))) + float(ca[K]['flips'])) / float(ca[K]['anneals'])
    pb = (float(cb[K].get('tests', cb[K].get('steps', 0))) + float(cb[K]['flips'])) / float(cb[K]['anneals'])
    cost[K] = dict(hostB=pa, hostA=pb, rel=pa / pb - 1)
d = int((x != y).sum())
r = dict(job=JOB, uses=len(x), uses_differ=d, frac=d / len(x), bits_hostB=int(x.sum()), bits_hostA=int(y.sum()),
         err_uses_hostB=int((x > 0).sum()), err_uses_hostA=int((y > 0).sum()), host_new=ia.get('host'), host_ref=ib.get('host'),
         counters_rel=rel, cost_per_anneal=cost, passed=d / len(x) <= 0.005)
r['pass'] = bool(r['passed'])
json.dump(r, open(OUT, 'w'), indent=1)
print('hz6 %s uses %d differ %d (%.2f%%) bits %d/%d err-uses %d/%d cost/anneal rel %s HZ6 %s' % (
    M, r['uses'], d, 100 * r['frac'], r['bits_hostB'], r['bits_hostA'], r['err_uses_hostB'], r['err_uses_hostA'],
    {K: '%+.1f%%' % (100 * v['rel']) for K, v in cost.items()}, 'PASS' if r['pass'] else 'FAIL'))
