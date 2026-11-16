#!/usr/bin/env python3
"""A5.20 analysis. Pure function of saved batches; no GPU.
Per k in (2, 4, inf): A_k / C64 (primary) and A_k / C0, each on the batch indices both arms have (seed 2028, batches of 500 uses).
A_k is this run's arm (ROOT/h4_c*) or, when S*_k is 64 or 480, A5.19's arm copied to REF (A64 / A*). C64 and C0 come from REF
(A5.19's held-out batches, copied read-only from hostA). Ratio of summed bit errors, a56an.boot_ratio (4,000 replicates, seed 12345),
exact McNemar. Terms: 'Arpeggio leads' (upper < 1), 'Chord leads' (lower > 1), else 'no detected difference'. A comparison with fewer
than 600 batches (time cut) is flagged partial. Also: every arm's held-out x per K (steps or tests + flips over A5.8 ref_cost), and the
check A_k's held-out x <= C64's held-out x * x_k(C64) / x_1(C64) on the primary's batches.
Usage: analyze_a520.py ROOT REF OUT.json   (src/ on sys.path)"""
import glob
import json
import os
import sys

import numpy as np

import a56an as AN

ROOT, REF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.exists(OUT):
    sys.exit('refusing: exists')
REF4 = {str(k): float(v) for k, v in json.load(open('<SCRATCH>/arpeggio_ber_20261024/results/a58/select.json'))['ref_cost'].items()}
SEL = json.load(open(os.path.join(ROOT, 'select.json')))
CN = json.load(open(os.path.join(ROOT, 'counts_a520.json')))
C0, C64 = 'a56_128_0.3_0.3_0.4_0_alt_8', 'abl_chord_0.2_0.2_0.2_rand_8'
REUSE = {'abl_far_64_0.1_0.1_0_bal_8', 'abl_far_480_0.1_0.1_0_bal_8'}
KS = (('2', 'c2'), ('4', 'c4'), ('inf', 'cinf'))
N4, BPU = 600, 256


def arm(root, m):
    out = {}
    for d in sorted(glob.glob(os.path.join(root, 'h4_c*', 'x64', m, 'snr_22.00'))):
        for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
            bi = int(os.path.basename(f)[1:6])
            z = np.load(f, allow_pickle=False)
            info = json.loads(str(z['info']))
            assert int(info['bi']) == bi and info['method'] == m and int(info.get('seed', 2028)) == 2028, f
            c = info.get('cnt', {})
            c = c.get('cnt', c) if isinstance(c, dict) else None
            assert bi not in out, ('duplicate batch', m, bi)
            out[bi] = (z['biterr'].astype(np.int64), c or None)
    return out


def xs(a, idx):
    tot = {}
    for bi in idx:
        c = a[bi][1]
        if not c:
            continue
        for K, v in c.items():
            if str(K).startswith('_'):
                continue
            t = tot.setdefault(str(K), [0.0, 0.0, 0.0])
            t[0] += float(v.get('tests', v.get('steps', 0.0))); t[1] += float(v['flips']); t[2] += float(v['anneals'])
    per = {K: (w + f) / n / REF4[K] for K, (w, f, n) in tot.items() if n}
    return dict(x_per_K=per, x=float(np.mean(list(per.values()))) if per else None)


def compare(a, b, lead, lag):
    idx = sorted(set(a) & set(b))
    if not idx:
        return None, idx
    x = np.concatenate([a[i][0] for i in idx]); y = np.concatenate([b[i][0] for i in idx])
    r, lo, hi = AN.boot_ratio(x, y)
    p, nx, ny = AN.mcnemar(x, y)
    c = dict(ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny, uses=int(len(x)), batches=len(idx), partial=len(idx) < N4,
             a_bit=int(x.sum()), b_bit=int(y.sum()), a_ber=float(x.sum()) / (len(x) * BPU), b_ber=float(y.sum()) / (len(y) * BPU),
             a_err_uses=int((x > 0).sum()), b_err_uses=int((y > 0).sum()))
    c['term'] = lead if hi < 1 else (lag if lo > 1 else 'no detected difference')
    return c, idx


assert CN.get('done') and CN['gates']['G2'] and CN['gates']['G2x'] and all(CN['gates']['G1_G3'].values())
xk = CN['x_k']
REFA = {C0: arm(REF, C0), C64: arm(REF, C64)}
out = dict(select=SEL, x_k_C64_calib=xk, ref_batches={m: len(v) for m, v in REFA.items()}, k={})
for k, key in KS:
    m = SEL['arms'].get(k)
    if not m:
        out['k'][k] = dict(note='no S* (calibration incomplete at the cut)')
        continue
    a = arm(REF, m) if m in REUSE else arm(ROOT, m)
    prim, idx = compare(a, REFA[C64], 'Arpeggio leads', 'Chord leads')
    sec, _ = compare(a, REFA[C0], 'Arpeggio leads', 'Chord leads')
    o = dict(S_star=SEL['S_star'][k], method=m, source='A5.19 (ref/)' if m in REUSE else 'A5.20', batches=len(a),
             x_k_C64=xk[key], A_C64=prim, A_C0=sec)
    if prim:
        xa, xc = xs(a, idx)['x'], xs(REFA[C64], idx)['x']
        lim = xc * xk[key] / xk['c1'] if xc else None
        o.update(held_x_A=xa, held_x_C64=xc, held_x_C64_k=lim, check_A_le_C64_k=(xa <= lim) if (xa and lim) else None)
    out['k'][k] = o
out['held_x'] = {m: xs(v, sorted(v)) for m, v in REFA.items()}
for k in out['k']:
    m = out['k'][k].get('method')
    if m and m not in out['held_x']:
        a = arm(REF, m) if m in REUSE else arm(ROOT, m)
        out['held_x'][m] = xs(a, sorted(a))
tmp = OUT + '.tmp'
with open(tmp, 'w') as f:
    json.dump(out, f, indent=1)
os.replace(tmp, OUT)
for k, o in out['k'].items():
    for nm in ('A_C64', 'A_C0'):
        c = o.get(nm)
        if c:
            print('k=%-3s S*=%-4s %-6s %.3f [%.3f, %.3f] p=%.2g batches=%d bits %d/%d %s%s' % (
                k, o['S_star'], nm, c['ratio'], c['lo'], c['hi'], c['mcnemar_p'], c['batches'], c['a_bit'], c['b_bit'], c['term'],
                ' (partial)' if c['partial'] else ''))
    if o.get('held_x_A'):
        print('k=%-3s held-out x: A %.4f, C64 %.4f, C64 at k %.4f, check %s' % (k, o['held_x_A'], o['held_x_C64'], o['held_x_C64_k'],
                                                                              o['check_A_le_C64_k']))
