#!/usr/bin/env python3
"""Post-hoc check, 8 Nov 2026 (outside PROTOCOL_A58 section 8; the frozen verdict is against float (i) and is unchanged).
Pairs the A5.8 B = 1 pick's 600 held-out batches (seed 344) with the production model's X3P x64 batches (Table IV row 6), index by index,
with the same estimators as analyze_a58.py / analyze_a56.py (a56an.boot_ratio, a56an.mcnemar). Also recomputes SA/float and production/float
as checks against analysis.json. CPU only. Usage: pair_a58_prod.py OUT.json"""
import glob, json, os, sys
import numpy as np
A = '<SCRATCH>/ap_ber_20261024'
sys.path.insert(0, os.path.join(A, 'src'))
import a56an as AN
R = os.path.join(A, 'results')
sel = json.load(open(os.path.join(R, 'a58', 'select.json')))
pick = sel['pick']

def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, 'b*.npz')):
        z = np.load(f, allow_pickle=False)
        out[int(os.path.basename(f)[1:6])] = z['biterr'].astype(np.int64)
    return out

sa = {}
for h in sel['held']:
    sa.update(load(os.path.join(R, 'a58', h, 'x64', pick, 'snr_22.00')))
prod = load(os.path.join(R, 'a56', 'X3P', 'x64', 'prod_fx_xs_8', 'snr_22.00'))
flt = load(os.path.join(R, 'a56', 'X64F', 'x64', 'a56_128_0.3_0.3_0.4_0_alt_8', 'snr_22.00'))
idx = list(range(600))
assert all(i in sa and i in prod and i in flt for i in idx)
assert all(len(sa[i]) == len(prod[i]) == len(flt[i]) == 500 for i in idx)
cat = lambda d: np.concatenate([d[i] for i in idx])
S, P, F = cat(sa), cat(prod), cat(flt)
res = dict(note=__doc__.split('\n')[0], pick=pick, uses=int(len(S)))
for nm, (a, b) in dict(sa_prod=(S, P), sa_float=(S, F), prod_float=(P, F)).items():
    r, lo, hi = AN.boot_ratio(a, b)
    p, nx, ny = AN.mcnemar(a, b)
    res[nm] = dict(ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny, a_err_uses=int((a > 0).sum()), b_err_uses=int((b > 0).sum()),
                   a_bit_err=int(a.sum()), b_bit_err=int(b.sum()), a_ber=float(a.sum()) / (len(a) * 256), b_ber=float(b.sum()) / (len(b) * 256))
json.dump(res, open(sys.argv[1], 'w'), indent=1)
print(json.dumps(res, indent=1))
