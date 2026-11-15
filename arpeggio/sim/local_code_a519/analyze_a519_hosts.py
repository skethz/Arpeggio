#!/usr/bin/env python3
"""A5.19 same-host sensitivity analysis. Identical to analyze_a519.py except that every pairing (comparisons and x_F) keeps only the batch indices
where both arms ran on the same host (info["host"]), and the output adds the host mix of every arm and comparison.
Pure function of saved batches; no GPU.
Each comparison pairs its two arms on the batch indices both have (P4: seed 2028, batches of 500; P1: batches of 2,000); x_F pairs
an arm with C0 the same way. If the time cut ended the run (fewer batches than planned), each comparison is flagged partial, and a
replication whose CI contains both 1 and the A5.8/A5.5 estimate (A64/C0 0.783, A5.8, seed 344; A16/C0 0.464, A5.5, seed 102) is 'inconclusive
(partial run)' instead of 'no detected difference'. Ratio of summed bit errors with a56an.boot_ratio (4,000 replicates, seed 12345) and exact
McNemar (a56an.mcnemar). Held-out cycles per K from the arms' counters: x = (steps or tests + flips) / anneals over default Chord's cost
(P4: A5.8 ref_cost on seed 1000; P1: L_K (1 + phi_K)), and x_F = the same over C0's own held-out cost (P4 only; P1's C0 has no counters).
Usage: analyze_a519_hosts.py ROOT OUT.json"""
import glob
import json
import os
import sys

import numpy as np

import a56an as AN

ROOT, OUT = sys.argv[1], sys.argv[2]
RES = os.path.dirname(os.path.abspath(ROOT))
PHI = json.load(open(os.path.join(RES, 'tuned_a52.json')))['flip_phi']
REF4 = {str(k): float(v) for k, v in json.load(open(os.path.join(RES, 'a58', 'select.json')))['ref_cost'].items()}
SEL = json.load(open(os.path.join(ROOT, 'select.json')))
BPU = dict(x64=256, x16=64)


def ref_cost(shape, K):
    return REF4[K] if shape == 'x64' else 256 * int(K) * (1 + PHI[shape][K])


def arm(tag, shape, m, snr):
    out = {}
    for d in sorted(glob.glob(os.path.join(ROOT, '%s_c*' % tag, shape, m, 'snr_%05.2f' % snr))):
        for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
            bi = int(os.path.basename(f)[1:6])
            z = np.load(f, allow_pickle=False)
            info = json.loads(str(z['info']))
            assert int(info['bi']) == bi and info['method'] == m
            c = info.get('cnt', {})
            c = c.get('cnt', c) if isinstance(c, dict) else None
            out[bi] = (z['biterr'].astype(np.int64), c or None, info.get('host'))
    return out


def cyc(a, idx):
    tot = {}
    for bi in idx:
        c = a[bi][1]
        if not c:
            continue
        for K, v in c.items():
            t = tot.setdefault(str(K), [0.0, 0.0, 0.0])
            t[0] += float(v.get('tests', v.get('steps', 0.0))); t[1] += float(v['flips']); t[2] += float(v['anneals'])
    return {K: (w + f) / n for K, (w, f, n) in tot.items() if n}


def xs(a, idx, shape, ref=None):
    c = cyc(a, idx)
    per = {K: v / ref_cost(shape, K) for K, v in c.items()}
    o = dict(cycles_per_K=c, x_per_K=per, x=float(np.mean(list(per.values()))) if per else None)
    if ref:
        pf = {K: v / ref[K] for K, v in c.items() if K in ref}
        o.update(x_F_per_K=pf, x_F=float(np.mean(list(pf.values()))) if pf else None)
    return o


def compare(a, b, idx, shape):
    if not idx:
        return None
    x = np.concatenate([a[i][0] for i in idx]); y = np.concatenate([b[i][0] for i in idx])
    r, lo, hi = AN.boot_ratio(x, y)
    p, nx, ny = AN.mcnemar(x, y)
    bpu = BPU[shape]
    return dict(ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny, uses=int(len(x)), batches=len(idx), first=idx[0], last=idx[-1],
                a_bit=int(x.sum()), b_bit=int(y.sum()), a_ber=float(x.sum()) / (len(x) * bpu), b_ber=float(y.sum()) / (len(y) * bpu),
                a_err_uses=int((x > 0).sum()), b_err_uses=int((y > 0).sum()))


def term(c, lead, lag, earlier=None):
    if c is None:
        return None
    t = lead if c['hi'] < 1 else (lag if c['lo'] > 1 else 'no detected difference')
    if t == 'no detected difference' and c['partial'] and earlier is not None and c['lo'] <= earlier <= c['hi']:
        t = 'inconclusive (partial run)'
    return t


def pair(a, b):
    return sorted(i for i in set(a) & set(b) if a[i][2] == b[i][2])


def mix(a, b=None):
    import collections
    if b is None:
        return dict(collections.Counter(str(v[2]) for v in a.values()))
    return dict(collections.Counter('%s/%s' % (a[i][2], b[i][2]) for i in set(a) & set(b)))


EARLIER = dict(A64_C0=0.783, A16_C0=0.464)
out = dict(select=SEL)
# ---------------- P4 (64x64 16-QAM, 22 dB, Ns 8), seed 2028
m4 = SEL['held4']
A4 = {k: arm('h4', 'x64', m, 22.0) for k, m in m4.items()}
X4 = {}
for k, v in A4.items():
    ic = pair(v, A4.get('C0', {}))
    X4[k] = dict(xs(v, ic, 'x64', cyc(A4['C0'], ic)), batches_with_C0=len(ic)) if ic else None
o = dict(methods=m4, batches={k: len(v) for k, v in A4.items()}, batches_expected=600, x=X4, hosts={k: mix(v) for k, v in A4.items()})
for nm, (p, q, lead, lag) in dict(primary_Astar_C64=('Astar', 'C64', 'Arpeggio leads', 'Chord leads'),
                                  A64_C0=('A64', 'C0', 'Arpeggio leads', 'Chord leads'),
                                  C64_C0=('C64', 'C0', 're-tuned leads', 'default leads'),
                                  Astar_C0=('Astar', 'C0', 'Arpeggio leads', 'Chord leads'),
                                  Astar_A64=('Astar', 'A64', 'A* leads', 'A64 leads')).items():
    c = None
    if p in A4 and q in A4:
        idx = pair(A4[p], A4[q])
        c = compare(A4[p], A4[q], idx, 'x64')
        if c:
            c['partial'] = len(idx) < 600
            c['host_pairs_all_common'] = mix(A4[p], A4[q])
            c['term'] = term(c, lead, lag, EARLIER.get(nm))
    o[nm] = c
if o['primary_Astar_C64']:
    idx = pair(A4['Astar'], A4['C64'])
    xa, xc = xs(A4['Astar'], idx, 'x64')['x'], xs(A4['C64'], idx, 'x64')['x']
    if xa and xc:
        o['astar_over_c64_cycles'] = xa / xc                                   # same indices, same ref_cost denominators
        o['astar_exceeds_c64_by_2pct'] = o['astar_over_c64_cycles'] > 1.02
out['P4'] = o
# ---------------- P1 (16x16 16-QAM, 20 dB, Ns 32), seed 2028
m1 = SEL['held1']
A1 = {k: arm('h1', 'x16', m, 20.0) for k, m in m1.items()}
idx1 = pair(A1['C0'], A1['A16'])
c = compare(A1['A16'], A1['C0'], idx1, 'x16')
if c:
    c['partial'] = len(idx1) < 150
    c['host_pairs_all_common'] = mix(A1['A16'], A1['C0'])
    c['term'] = term(c, 'Arpeggio leads', 'Chord leads', EARLIER['A16_C0'])
out['P1'] = dict(methods=m1, hosts={k: mix(v) for k, v in A1.items()}, batches={k: len(v) for k, v in A1.items()}, batches_both=len(idx1), batches_expected=150, A16_C0=c,
                 x={k: xs(v, idx1, 'x16') for k, v in A1.items()})
tmp = OUT + '.tmp'
with open(tmp, 'w') as f:
    json.dump(out, f, indent=1)
os.replace(tmp, OUT)


def show(name, c):
    if c:
        print('%-22s %.3f [%.3f, %.3f] p=%.2g uses=%d bits %d/%d err-uses %d/%d %s' % (
            name, c['ratio'], c['lo'], c['hi'], c['mcnemar_p'], c['uses'], c['a_bit'], c['b_bit'], c['a_err_uses'], c['b_err_uses'],
            c.get('term', '')) + (' (partial)' if c.get('partial') else ''))


for k in ('primary_Astar_C64', 'A64_C0', 'C64_C0', 'Astar_C0', 'Astar_A64'):
    show('P4 ' + k, out['P4'][k])
show('P1 A16_C0', out['P1']['A16_C0'])
print('P4 x_F (C0 = 1):', {k: round(v['x_F'], 4) for k, v in out['P4']['x'].items() if v and v.get('x_F') is not None})
