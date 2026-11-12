#!/usr/bin/env python3
"""A5.8 analysis (PROTOCOL_A58.md sections 7-8; written 7 Nov 2026 before any held-out result). No GPU.
Usage: analyze_a58.py ROOT X64F_DIR   (ROOT = .../results/a58; X64F_DIR = .../results/a56/X64F/x64/<REF>/snr_22.00). Writes ROOT/analysis.json.
Pairs the B = 1 pick's held-out batches (sets held0..held5, seed 344) with X64F's batches of the same index. Ratio SA/(i) of bit errors,
paired cluster bootstrap (a56an.boot_ratio, 4,000) and exact McNemar on erroneous uses. x_F = mean over K of SA (tests + flips) / anneals
over (i)'s L_K + F_K, both counted on the paired batches. A time cut uses every completed batch (section 6)."""
import glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

ROOT, XF = sys.argv[1], sys.argv[2]
BPU, RMAX, XMAX = 256, 3, 1.10
sel = json.load(open(os.path.join(ROOT, 'select.json')))
pick = sel['pick']
if pick is None:
    raise SystemExit('no B = 1 pick yet')


def batches(d):
    out = {}
    for f in glob.glob(os.path.join(d, 'b*.npz')):
        z = np.load(f, allow_pickle=False)
        info = json.loads(str(z['info']))
        c = info.get('cnt', {})
        c = c.get('cnt', c)
        out[int(info['bi'])] = (z['biterr'].astype(np.int64), c, info)
    return out


sa = {}
for h in sel['held']:
    sa.update(batches(os.path.join(ROOT, h, 'x64', pick, 'snr_22.00')))
ref = batches(XF)
common = sorted(set(sa) & set(ref))
for bi in common:
    assert len(sa[bi][0]) == len(ref[bi][0]) == 500, bi
a = np.concatenate([sa[bi][0] for bi in common])
b = np.concatenate([ref[bi][0] for bi in common])
r, lo, hi = AN.boot_ratio(a, b)
p, nx, ny = AN.mcnemar(a, b)


def sums(bs, keys):
    t = {}
    for bi in common:
        for K, v in bs[bi][1].items():
            d = t.setdefault(str(K), {k: 0.0 for k in keys})
            for k in keys:
                d[k] += float(v.get(k, 0.0))
    return t


ts, tr = sums(sa, ('tests', 'flips', 'anneals')), sums(ref, ('flips', 'anneals'))
xk = {}
for K in range(1, RMAX + 1):
    s, q = ts.get(str(K)), tr.get(str(K))
    if s and q and s['anneals'] and q['anneals']:
        xk[str(K)] = dict(sa=(s['tests'] + s['flips']) / s['anneals'], ref=256 * K + q['flips'] / q['anneals'])
        xk[str(K)]['x'] = xk[str(K)]['sa'] / xk[str(K)]['ref']
xF = float(np.mean([v['x'] for v in xk.values()]))
term = 'antiphase_leads' if lo > 1 else ('sa_leads' if hi < 1 else 'no_detected_difference')
res = dict(note='A5.8: first-accept SA (rule (2), model F) re-tuned for B = 1 vs Antiphase (i) at P4 = 64x64 16-QAM, 22 dB, Ns 8; seed 344; '
                'ratio SA/(i); modeled cycles only; exploratory.',
           pick=pick, batches=len(common), batches_expected=600, uses=int(len(a)), sa_err_uses=int((a > 0).sum()), ref_err_uses=int((b > 0).sum()),
           sa_bit_err=int(a.sum()), ref_bit_err=int(b.sum()), sa_ber=float(a.sum()) / (len(a) * BPU), ref_ber=float(b.sum()) / (len(b) * BPU),
           ratio=r, lo=lo, hi=hi, mcnemar_p=p, sa_only=nx, ref_only=ny, x_F=xF, x_F_per_K=xk,
           x_F_stage_a=sel['stage_a_x'].get(pick), term=term, within_budget=xF <= XMAX,
           label=None if xF <= XMAX else 'at x_F = %.2f (above the 1.10 budget check)' % xF, select=sel)
tmp = os.path.join(ROOT, 'analysis.json.tmp')
with open(tmp, 'w') as f:
    json.dump(res, f, indent=1)
os.replace(tmp, os.path.join(ROOT, 'analysis.json'))
print(json.dumps({k: res[k] for k in ('pick', 'batches', 'uses', 'sa_err_uses', 'ref_err_uses', 'ratio', 'lo', 'hi', 'mcnemar_p', 'x_F', 'term', 'label')}))
