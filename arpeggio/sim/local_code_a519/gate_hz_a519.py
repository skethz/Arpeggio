#!/usr/bin/env python3
"""A5.19 host gate HZ (ADDENDUM_A519_HOSTA.md section 4). hostA reruns five stored hostB batches, one per worker path:
HZ1 A64 (P4, seed 344, A5.8 held0 b0), HZ2 C0 (P4, seed 344, X64F b0), HZ3 a re-tune cell (P4, seed 1000, A5.19 stage A b0, hostB),
HZ4 A16 (P1, seed 102, A5.5 b0), HZ5 mdiane32 (P1, seed 102, b0). The jobs carry no 'saved' key (no bit-for-bit assertion); this
script compares per-use bit errors and counters with the stored files. Pass: in each, at most 0.5% of uses differ (the G4 bound).
Usage: gate_hz_a519.py plan ROOT REFDIR | compare ROOT REFDIR OUT.json"""
import json
import os
import sys

import numpy as np

JOBS = [
    ('hz1', dict(shape='x64', method='abl_far_64_0.1_0.1_0_bal_8', snr=22.0, seed=344, batch=500)),
    ('hz2', dict(shape='x64', method='a56_128_0.3_0.3_0.4_0_alt_8', stream='mdiane8', snr=22.0, seed=344, batch=500)),
    ('hz3', dict(shape='x64', method='abl_ape_0.3_0.3_0.4_rand_8', snr=22.0, seed=1000, batch=500)),
    ('hz4', dict(shape='x16', method='abl_far_64_0.1_0.1_0_rand_32', snr=20.0, seed=102, batch=2000)),
    ('hz5', dict(shape='x16', method='mdiane32', snr=20.0, seed=102, batch=2000)),
]
mode, ROOT, REF = sys.argv[1], sys.argv[2], sys.argv[3]
if mode == 'plan':
    os.makedirs(ROOT, exist_ok=True)
    jobs = [dict(set=s, first_batch=0, n_batches=1, **j) for s, j in JOBS]
    json.dump(dict(jobs=jobs), open(os.path.join(ROOT, 'plan.json'), 'w'), indent=1)
    print('wrote', len(jobs), 'jobs')
    sys.exit(0)


def cnt(info):
    c = info.get('cnt') or {}
    return c.get('cnt', c) if isinstance(c, dict) else {}


out, ok = {}, True
for s, j in JOBS:
    new = os.path.join(ROOT, s, j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'b00000.npz')
    ref = os.path.join(REF, s, 'b00000.npz')
    a, b = np.load(new), np.load(ref)
    x, y = a['biterr'].astype(np.int64), b['biterr'].astype(np.int64)
    ia, ib = json.loads(str(a['info'])), json.loads(str(b['info']))
    ca, cb = cnt(ia), cnt(ib)
    rel = {}
    for K in sorted(set(ca) & set(cb)):
        for f in ('flips', 'tests', 'steps', 'anneals'):
            if f in ca[K] and f in cb[K] and float(cb[K][f]):
                rel['%s_%s' % (K, f)] = float(ca[K][f]) / float(cb[K][f]) - 1
    d = int((x != y).sum())
    r = dict(uses=len(x), uses_differ=d, frac=d / len(x), bits_new=int(x.sum()), bits_ref=int(y.sum()), err_uses_new=int((x > 0).sum()),
             err_uses_ref=int((y > 0).sum()), host_new=ia.get('host'), host_ref=ib.get('host'), counters_compared=len(rel),
             max_abs_counter_rel=max((abs(v) for v in rel.values()), default=None), passed=d / len(x) <= 0.005)
    ok &= r['passed']
    out[s] = dict(job=j, **r)
    print('%s %-30s uses %d differ %d (%.2f%%) bits %d/%d err-uses %d/%d counters %d max|rel| %s %s' % (
        s, j['method'], r['uses'], d, 100 * r['frac'], r['bits_new'], r['bits_ref'], r['err_uses_new'], r['err_uses_ref'],
        r['counters_compared'], '%.2e' % r['max_abs_counter_rel'] if r['max_abs_counter_rel'] is not None else '-',
        'PASS' if r['passed'] else 'FAIL'))
out['pass'] = bool(ok)
json.dump(out, open(sys.argv[4], 'w'), indent=1)
print('HZ', 'PASS' if ok else 'FAIL')
