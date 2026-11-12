#!/usr/bin/env python3
"""A5.17 S3 analysis (AMENDMENTS_A517.md A1). Pure function of saved batches; functions as in analyze_a514.py (A5.15 sec. 5-6).
Per k in {2, 4, inf}: S*_k = largest grid S with calibration x(S) <= x_k(C1) (plan.json 'grid'/'thresholds', recomputed here);
primary A*_k / C1 (paired bootstrap of summed bit errors, 4,000 replicates, seed 12345; exact McNemar) on the batch indices every
arm has; also A*_k / C0 and every arm's held-out x per K; check (not a decision): x_held(A*_k) <= x_held(C1) * x_k(C1) / x_1(C1).
Usage (on hostB, from src/): s3_analyze.py RESULTS_DIR OUT.json"""
import glob
import json
import os
import sys

import numpy as np

import a56an as AN

RES, OUT = sys.argv[1], sys.argv[2]
PHI = json.load(open(os.path.join(RES, 'tuned_a52.json')))['flip_phi']
PLAN = json.load(open(os.path.join(RES, 'a517s3', 'plan.json')))
X1_C1 = 1.1204                                                           # A1: C1 at k = 1 on A5.15's calibration batch
SNR, SH = 22.0, 'x32'


def ref_cost(K):
    return 256 * int(K) * (1 + PHI[SH][K])


def arm(dirs):
    out = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
            bi = int(os.path.basename(f)[1:6])
            if bi in out:
                continue
            z = np.load(f, allow_pickle=False)
            info = json.loads(str(z['info']))
            c = info.get('cnt', info.get('count'))
            if isinstance(c, dict) and 'cnt' in c:
                c = c['cnt']
            out[bi] = (z['biterr'].astype(np.int64), c if isinstance(c, dict) else None)
    return out


def xs(a, keep):
    tot = {}
    for bi, (_, c) in sorted(a.items()):
        if bi not in keep or not c:
            continue
        for K, v in c.items():
            if isinstance(v, list):
                v = dict(flips=v[0], tests=v[1], anneals=v[2])
            t = tot.setdefault(str(K), [0.0, 0.0, 0.0])
            t[0] += float(v.get('tests', v.get('steps', 0))); t[1] += float(v['flips']); t[2] += float(v['anneals'])
    per = {K: (w + f) / n / ref_cost(K) for K, (w, f, n) in sorted(tot.items()) if n}
    return dict(per_K=per, x=float(np.mean(list(per.values()))) if per else None)


def compare(a, b, common):
    x = np.concatenate([a[i][0] for i in common]); y = np.concatenate([b[i][0] for i in common])
    r, lo, hi = AN.boot_ratio(x, y)
    p, nx, ny = AN.mcnemar(x, y)
    bpu = 2 * 32 * 2
    return dict(ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny, uses=int(len(x)), batches=len(common),
                first=common[0], last=common[-1], a_bit=int(x.sum()), b_bit=int(y.sum()), a_ber=float(x.sum()) / (len(x) * bpu),
                b_ber=float(y.sum()) / (len(y) * bpu))


def term(c):
    return 'Arpeggio leads' if c['hi'] < 1 else ('Chord leads' if c['lo'] > 1 else 'no detected difference')


def d515(m):
    return sorted(glob.glob(os.path.join(RES, 'a514', 'a515_c*', SH, m, 'snr_%05.2f' % SNR)))


def d517(m):
    return sorted(glob.glob(os.path.join(RES, 'a517s3', 'a517_c*', SH, m, 'snr_%05.2f' % SNR)))


grid = {int(s): float(v) for s, v in PLAN['grid'].items()}
sstar = {}
for k, thr in PLAN['thresholds'].items():
    ok = [s for s, v in grid.items() if v <= thr]
    sstar[k] = max(ok)
assert sstar == {k: int(v) for k, v in PLAN['sstar'].items()}, (sstar, PLAN['sstar'])

C1 = arm(d515('abl_ape_0.2_0.2_0.2_rand_8')); C0 = arm(d515('mdiane8')); A76 = arm(d515('abl_far_76_0.1_0.1_0_rand_8'))
A = {S: arm(d517('abl_far_%d_0.1_0.1_0_rand_8' % S)) for S in sorted(set(sstar.values()))}
common = sorted(set(C1) & set(C0) & set(A76) & set.intersection(*[set(v) for v in A.values()]))
keep = set(common)
out = dict(sstar=sstar, thresholds=PLAN['thresholds'], x1_C1=X1_C1, batches=len(common), first=common[0], last=common[-1],
           x=dict(C1=xs(C1, keep), C0=xs(C0, keep), A76=xs(A76, keep), **{'A%d' % S: xs(v, keep) for S, v in A.items()}))
xc1 = out['x']['C1']['x']
for k, S in sstar.items():
    p = compare(A[S], C1, common); p['term'] = term(p)
    q = compare(A[S], C0, common); q['term'] = term(q)
    xa = out['x']['A%d' % S]['x']; bound = xc1 * PLAN['thresholds'][k] / X1_C1
    out['k=' + k] = dict(S=S, primary_A_C1=p, A_C0=q, x_held_A=xa, check_bound=bound, check_holds=bool(xa <= bound))
out['ref_A76_C1'] = compare(A76, C1, common); out['ref_A76_C1']['term'] = term(out['ref_A76_C1'])
json.dump(out, open(OUT, 'w'), indent=1)

print('S*', sstar, 'batches', len(common), common[0], common[-1])
for nm, v in out['x'].items():
    if v['x'] is None:
        print('x_held %-4s (no counters)' % nm); continue
    print('x_held %-4s %.4f  %s' % (nm, v['x'], ' '.join('K%s %.4f' % kv for kv in v['per_K'].items())))
for k in sstar:
    o = out['k=' + k]
    for nm in ('primary_A_C1', 'A_C0'):
        c = o[nm]
        print('k=%-3s S=%d %-13s %.3f [%.3f, %.3f] McNemar p=%.2g bits %d/%d uses %d  %s' % (
            k, o['S'], nm, c['ratio'], c['lo'], c['hi'], c['mcnemar_p'], c['a_bit'], c['b_bit'], c['uses'], c['term']))
    print('k=%-3s check: x_held(A*) %.4f <= %.4f ? %s' % (k, o['x_held_A'], o['check_bound'], o['check_holds']))
c = out['ref_A76_C1']
print('ref A76/C1 (A5.15 primary) %.3f [%.3f, %.3f] %s' % (c['ratio'], c['lo'], c['hi'], c['term']))
