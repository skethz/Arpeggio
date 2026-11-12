# Exploratory cross-check (not PROTOCOL_A55 section 9): A5.4 Antiphase budget series vs A5.5 re-tuned SA per-S picks at nearest modeled cycles.
import json, math, os, sys
sys.path.insert(0, '<SCRATCH>/ap_ber_20261024/src')
sys.argv = ['x', '<SCRATCH>/ap_ber_20261024/results']
import importlib.util
spec = importlib.util.spec_from_file_location('an55', '<SCRATCH>/ap_ber_20261024/src/analyze_a55.py')
RES = '<SCRATCH>/ap_ber_20261024/results'
A54 = json.load(open(RES + '/a54/analysis.json'))
A55 = json.load(open(RES + '/a55/analysis.json'))
import numpy as np, glob
sys.path.insert(0, '<SCRATCH>/ap_ber_20261024/src'); import a56an as AN
def load(d):
    fs = sorted(glob.glob(d + '/b*.npz')); zs = [np.load(f) for f in fs]
    return [z['biterr'].astype(np.int64) for z in zs]
def pair(a, b):
    nb = 0
    for x, y in zip(a, b):
        if len(x) != len(y): break
        nb += 1
    x, y = np.concatenate(a[:nb]), np.concatenate(b[:nb])
    r, lo, hi = AN.boot_ratio(x, y); return r, lo, hi, len(x)
PT = {'P1': ('x16', 20.0, 32), 'P2': ('x32', 22.0, 8)}
for pt, (sh, snr, Ns) in PT.items():
    rows = A54['points'][pt]['rows']
    ps = A55['points'][pt]['per_s']
    for arm, xk in (('fam', 'x_E'), ('far', 'x_F'), ('fam', 'x_F')):
        for k, v in sorted(ps.items(), key=lambda t: int(t[0].split('/')[1])):
            if not k.startswith(arm + '/'): continue
            S = int(k.split('/')[1]); xs = v[xk]
            if xs < 0.9: continue
            best = min(rows, key=lambda r: abs(math.log(r['cyc_ratio']) - math.log(xs)))
            a = load('%s/a54/abl/%s/abl_anel_%d_%d/snr_%05.2f' % (RES, sh, best['Sk'], Ns, snr))
            b = load('%s/a55/abl/%s/%s/snr_%05.2f' % (RES, sh, v['method'], snr))
            r, lo, hi, n = pair(a, b)
            print('%s %s-%s S %3d x %.2f | Antiphase Sk %4d x %.2f | AP/SA %.3f [%.3f, %.3f] uses %d' % (pt, arm, xk, S, xs, best['Sk'], best['cyc_ratio'], r, lo, hi, n))
