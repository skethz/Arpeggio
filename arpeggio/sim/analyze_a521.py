#!/usr/bin/env python3
"""A5.21 analysis. Pure function of saved batches; no GPU.
Per point (P1, P2): SA / C0 on the batch indices both arms have (seed 2028). Ratio of summed bit errors, a56an.boot_ratio (4,000
replicates, seed 12345), exact McNemar. Terms: 'Chord leads' (lower > 1), 'SA leads' (upper < 1), else 'no detected difference';
partial if fewer batches than planned, and 'inconclusive (partial run)' if a partial CI holds both 1 and A5.5's estimate.
Check: SA's held-out x_E per K = (decisions + flips) / anneals over A5.5's L + phi_K L (L = 256 K, tuned_a52 flip_phi).
Usage: analyze_a521.py ROOT OUT.json   (src/ on sys.path)"""
import glob, json, os, sys
import numpy as np
import a56an as AN
ROOT, OUT = sys.argv[1], sys.argv[2]
if os.path.exists(OUT):
    sys.exit('refusing: exists')
PHI = json.load(open('<SCRATCH>/arpeggio_ber_20261024/results/tuned_a52.json'))['flip_phi']
PTS = {'P1': dict(sh='x16', snr=20.0, N=150, bpu=64, C0='mdichord32', SA='abl_fam_4_0.3_0.15_rand_32', S=4, a55=2.5104895104895104,
                  a55_xE=0.89778083027385),
       'P2': dict(sh='x32', snr=22.0, N=300, bpu=128, C0='mdichord8', SA='abl_fam_2_0.2_0.2_bal_8', S=2, a55=5.219753086419753,
                  a55_xE=0.7058261181076629)}
SEL = json.load(open(os.path.join(ROOT, 'select.json')))
assert all(SEL['gates'].values()) and not SEL['gate_failed'], SEL


def arm(pt, m):
    p = PTS[pt]
    out = {}
    for d in sorted(glob.glob(os.path.join(ROOT, 'h_%s_c*' % pt, p['sh'], m, 'snr_%05.2f' % p['snr']))):
        for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
            bi = int(os.path.basename(f)[1:6])
            z = np.load(f, allow_pickle=False)
            info = json.loads(str(z['info']))
            assert int(info['bi']) == bi and info['method'] == m, f
            c = info.get('cnt', {})
            c = c.get('cnt', c) if isinstance(c, dict) else None
            assert bi not in out, ('duplicate batch', m, bi)
            out[bi] = (z['biterr'].astype(np.int64), c or None)
    return out


def x_E(pt, a, idx):
    tot = {}
    for bi in idx:
        for K, v in (a[bi][1] or {}).items():
            if str(K).startswith('_'):
                continue
            t = tot.setdefault(str(K), [0.0, 0.0, 0.0])
            t[0] += float(v.get('decisions', np.nan)); t[1] += float(v['flips']); t[2] += float(v['anneals'])
    sh = PTS[pt]['sh']
    per = {K: (d + f) / n / (256 * int(K) * (1 + PHI[sh][K])) for K, (d, f, n) in tot.items() if n and K in PHI[sh]}
    return dict(x_E_per_K=per, x_E=float(np.mean(list(per.values()))) if per else None)


out = dict(select=SEL, points={})
for pt, p in PTS.items():
    s, c = arm(pt, p['SA']), arm(pt, p['C0'])
    idx = sorted(set(s) & set(c))
    o = dict(SA=p['SA'], C0=p['C0'], batches_SA=len(s), batches_C0=len(c), a55_ratio=p['a55'], a55_x_E=p['a55_xE'])
    if idx:
        x = np.concatenate([s[i][0] for i in idx]); y = np.concatenate([c[i][0] for i in idx])
        r, lo, hi = AN.boot_ratio(x, y)
        pv, nx, ny = AN.mcnemar(x, y)
        part = len(idx) < p['N']
        term = 'Chord leads' if lo > 1 else ('SA leads' if hi < 1 else 'no detected difference')
        if part and lo <= 1 <= hi and lo <= p['a55'] <= hi:
            term = 'inconclusive (partial run)'
        o.update(ratio=r, lo=lo, hi=hi, mcnemar_p=pv, sa_only=nx, c0_only=ny, uses=int(len(x)), batches=len(idx), partial=part, term=term,
                 sa_bit=int(x.sum()), c0_bit=int(y.sum()), sa_ber=float(x.sum()) / (len(x) * p['bpu']),
                 c0_ber=float(y.sum()) / (len(y) * p['bpu']), sa_err_uses=int((x > 0).sum()), c0_err_uses=int((y > 0).sum()))
        o.update(x_E(pt, s, idx))
    out['points'][pt] = o
tmp = OUT + '.tmp'
with open(tmp, 'w') as f:
    json.dump(out, f, indent=1)
os.replace(tmp, OUT)
for pt, o in out['points'].items():
    if 'ratio' in o:
        print('%s SA/C0 %.3f [%.3f, %.3f] p=%.2g batches=%d uses=%d bits %d/%d %s%s; x_E %s (A5.5 %.3f)' % (
            pt, o['ratio'], o['lo'], o['hi'], o['mcnemar_p'], o['batches'], o['uses'], o['sa_bit'], o['c0_bit'], o['term'],
            ' (partial)' if o['partial'] else '', ('%.3f' % o['x_E']) if o.get('x_E') else None, o['a55_x_E']))
    else:
        print(pt, 'no common batches')
