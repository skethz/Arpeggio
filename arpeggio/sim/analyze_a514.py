#!/usr/bin/env python3
"""A5.14-A5.16 analysis (PROTOCOL_A514.md 6-7, PROTOCOL_A515.md 6-7, PROTOCOL_A516.md 5-6). Pure function of saved batches.
Pairs two arms on the batch indices both have (file bNNNNN.npz = global batch index), concatenates per-use bit errors in batch order,
and reports the ratio of summed bit errors with a56an.boot_ratio (4,000 replicates, seed 12345) and a56an.mcnemar, plus held-out
cycles per K (x) where counters exist. Usage: analyze_a514.py ROOT OUT.json"""
import glob
import json
import os
import sys

import numpy as np

import a56an as AN

ROOT, OUT = sys.argv[1], sys.argv[2]
RES = os.path.dirname(os.path.abspath(ROOT))                               # .../results
PHI = json.load(open(os.path.join(RES, 'tuned_a52.json')))['flip_phi']
REF4 = {str(k): float(v) for k, v in json.load(open(os.path.join(RES, 'a58/select.json')))['ref_cost'].items()}
SEL = json.load(open(os.path.join(ROOT, 'select_a514.json')))


def ref_cost(shape, K):
    return REF4[K] if shape == 'x64' else 256 * int(K) * (1 + PHI[shape][K])


def arm(dirs, shape):
    """bi -> (biterr uint8 array, counters or None) over every directory given (later directories never override earlier)."""
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


def xs(a, shape):
    tot = {}
    for _, (_, c) in sorted(a.items()):
        if not c:
            continue
        for K, v in c.items():
            if isinstance(v, list):                                        # run_a513 counters: [flips, tests, anneals]
                v = dict(flips=v[0], tests=v[1], anneals=v[2])
            t = tot.setdefault(str(K), [0.0, 0.0, 0.0])
            work = v.get('tests', v.get('steps', 0))
            t[0] += float(work); t[1] += float(v['flips']); t[2] += float(v['anneals'])
    per = {K: (w + f) / n / ref_cost(shape, K) for K, (w, f, n) in tot.items() if n}
    return dict(per_K=per, x=float(np.mean(list(per.values()))) if per else None)


def compare(a, b, shape, bmax=None):
    common = sorted(set(a) & set(b))
    if bmax is not None:
        common = [i for i in common if i < bmax]
    if not common:
        return None
    x = np.concatenate([a[i][0] for i in common]); y = np.concatenate([b[i][0] for i in common])
    r, lo, hi = AN.boot_ratio(x, y)
    p, nx, ny = AN.mcnemar(x, y)
    bpu = 2 * {'x16': 16, 'x32': 32, 'x64': 64}[shape] * 2
    return dict(ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny, uses=int(len(x)), batches=len(common),
                first=common[0], last=common[-1], a_bit=int(x.sum()), b_bit=int(y.sum()), a_ber=float(x.sum()) / (len(x) * bpu),
                b_ber=float(y.sum()) / (len(y) * bpu), a_err_uses=int((x > 0).sum()), b_err_uses=int((y > 0).sum()))


def term(c, lead, lag):
    if c is None:
        return None
    return lead if c['hi'] < 1 else (lag if c['lo'] > 1 else 'no detected difference')


def chunk_dirs(tag, shape, m, snr):
    return sorted(glob.glob(os.path.join(ROOT, '%s_c*' % tag, shape, m, 'snr_%05.2f' % snr)))


out = {}
# ---------------- A5.15 (P2, seed 2027)
m15 = dict(C0='mdiane8', C1='abl_ape_0.2_0.2_0.2_rand_8', Astar=SEL['A515']['method'], A32='abl_far_32_0.1_0.1_0_rand_8')
A15 = {k: arm(chunk_dirs('a515', 'x32', m, 22.0), 'x32') for k, m in m15.items()}
o = dict(methods=m15, x={k: xs(v, 'x32') for k, v in A15.items()})
for nm, (p, q) in dict(primary_Astar_C1=('Astar', 'C1'), A32_C0=('A32', 'C0'), C1_C0=('C1', 'C0'), Astar_C0=('Astar', 'C0'),
                       Astar_A32=('Astar', 'A32')).items():
    c = compare(A15[p], A15[q], 'x32')
    if c:
        c['term'] = term(c, 'Arpeggio leads' if p != 'C1' else 're-tuned leads', 'Chord leads' if p != 'C1' else 'default leads')
    o[nm] = c
out['A515'] = o

# ---------------- A5.16 stage 1 (float extension vs A5.13 fixed)
FL = dict(P1=('x16', 20.0, 'abl_far_64_0.1_0.1_0_rand_32'), P2=('x32', 22.0, 'abl_far_32_0.1_0.1_0_rand_8'),
          P4=('x64', 22.0, 'abl_far_64_0.1_0.1_0_bal_8'))


def w1_dirs(pt):
    sh, snr, m = FL[pt]
    if pt == 'P4':
        return sorted(glob.glob(os.path.join(RES, 'a58', 'held*', sh, m, 'snr_%05.2f' % snr)))
    return [os.path.join(RES, 'a55', 'abl', sh, m, 'snr_%05.2f' % snr)] + chunk_dirs('a516f', sh, m, snr)


W1 = {pt: arm(w1_dirs(pt), FL[pt][0]) for pt in FL}
o = {}
for pt, (sh, snr, m) in FL.items():
    fx = arm([os.path.join(ROOT, 'a513_fixed', sh, m.replace('abl_far_', 'fafx_'), 'snr_%05.2f' % snr)], sh)
    c = compare(fx, W1[pt], sh)
    if c:
        c['term'] = term(c, 'fixed better', 'fixed worse'); c['passes_1.10'] = c['hi'] < 1.10
    o[pt] = dict(all=c, a513_batches=compare(fx, W1[pt], sh, bmax={'P1': 14, 'P2': 43, 'P4': 600}[pt]),
                 float_x=xs(W1[pt], sh), fixed_x=xs(fx, sh))
out['A516_stage1'] = o

# ---------------- A5.16 stage 2 (fixed variants at P1, hostB)
o = {}
sh, snr, m = FL['P1']
V = {}
for v, nm in dict(V0='fafx_', V1='fafxq16_', V2='fafxka516_').items():
    V[v] = arm([os.path.join(ROOT, 'a516x', 'x16', m.replace('abl_far_', nm), 'snr_%05.2f' % snr)], sh)
for nm, (p, q) in dict(V1_V0=('V1', 'V0'), V2_V0=('V2', 'V0'), V0_float=('V0', None), V1_float=('V1', None),
                       V2_float=('V2', None)).items():
    c = compare(V[p], V[q] if q else W1['P1'], sh)
    if c:
        c['term'] = term(c, 'lower', 'higher'); c['passes_1.10'] = c['hi'] < 1.10
    o[nm] = c
out['A516_stage2'] = o

# ---------------- A5.14 (W vs W = 1)
o = {}
for pt, (sh, snr, m) in FL.items():
    for W in (2, 4):
        mw = SEL['A514']['%s/W%d' % (pt, W)]['method']
        a = arm(chunk_dirs('a514', sh, mw, snr), sh)
        c = compare(a, W1[pt], sh)
        if c:
            c['term'] = term(c, 'W helps', 'W hurts')
        o['%s/W%d' % (pt, W)] = dict(method=mw, cmp=c, x=xs(a, sh), x_W1=xs(W1[pt], sh) if W == 2 else None)
for W in (2, 4):
    t = [o['%s/W%d' % (pt, W)]['cmp'] and o['%s/W%d' % (pt, W)]['cmp']['term'] for pt in FL]
    have = [x for x in t if x]
    helps, hurts = have.count('W helps'), have.count('W hurts')
    if len(have) == 3:
        v = 'helps' if helps >= 2 and hurts == 0 else ('hurts' if hurts >= 2 and helps == 0 else 'mixed or unresolved')
    elif len(have) == 2 and t[2] is None:
        v = 'helps' if helps == 2 else ('hurts' if hurts == 2 else 'mixed or unresolved')
    else:
        v = 'incomplete'
    o['decision_W%d' % W] = dict(terms=t, verdict=v)
out['A514'] = o
json.dump(out, open(OUT, 'w'), indent=1)


def show(name, c):
    if c:
        print('%-28s %.3f [%.3f, %.3f] p=%.2g uses=%d bits %d/%d %s' % (name, c['ratio'], c['lo'], c['hi'], c['mcnemar_p'], c['uses'],
                                                                        c['a_bit'], c['b_bit'], c.get('term', '')))


for k in ('primary_Astar_C1', 'A32_C0', 'C1_C0', 'Astar_C0', 'Astar_A32'):
    show('A5.15 ' + k, out['A515'][k])
for pt in FL:
    show('A5.16 s1 %s fixed/float' % pt, out['A516_stage1'][pt]['all'])
for k, c in out['A516_stage2'].items():
    show('A5.16 s2 ' + k, c)
for k, v in out['A514'].items():
    if k.startswith('decision'):
        print(k, v)
    else:
        show('A5.14 ' + k, v['cmp'])
