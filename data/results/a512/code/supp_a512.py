#!/usr/bin/env python3
"""A5.12 supplementary (written after the analysis, not in PROTOCOL_A512): BER ratio PT/(i) against (i)'s FULL held-out run, as A5d
reported its 1.40/14/2,500 (stats_ap convention: the common prefix is resampled with one index vector for both, the tails beyond the
shorter run independently; cluster bootstrap over uses, B = 4000, percentile 95 %). Usage: supp_a512.py ROOT REF_ROOT"""
import glob, json, os, sys
import numpy as np
ROOT, REF = sys.argv[1], sys.argv[2]
PT = {'P1': ('x16', 20.0, 32, 'mdiane32', 64), 'P2': ('x32', 22.0, 8, 'mdiane8', 128), 'P3': ('q32', 14.0, 8, 'mdiane8', 64)}
def be(d):
    fs = sorted(glob.glob(os.path.join(d, 'b*.npz')))
    return [np.load(f)['biterr'].astype(np.int64) for f in fs]
def common(a, b):
    n = 0
    for x, y in zip(a, b):
        if len(x) != len(y): break
        n += 1
    return n
out = {}
rng = np.random.default_rng(2024)
for pt, (sh, snr, Ns, refm, bpu) in PT.items():
    r = be(os.path.join(REF, 'abl', sh, refm, 'snr_%05.2f' % snr))
    for c in (5, 3, 2):
        a = be(os.path.join(ROOT, 'abl', sh, 'abl_pt12c%d_%d' % (c, Ns), 'snr_%05.2f' % snr))
        nb = common(a, r)
        ac, rc = np.concatenate(a[:nb]), np.concatenate(r[:nb])
        at = np.concatenate(a[nb:]) if len(a) > nb else np.zeros(0, np.int64)
        rt = np.concatenate(r[nb:]) if len(r) > nb else np.zeros(0, np.int64)
        na, nr = len(ac) + len(at), len(rc) + len(rt)
        ber_a, ber_r = (ac.sum() + at.sum()) / (na * bpu), (rc.sum() + rt.sum()) / (nr * bpu)
        reps = np.empty(4000); m = len(ac)
        for k in range(4000):
            i = rng.integers(0, m, m)
            sa = ac[i].sum() + (at[rng.integers(0, len(at), len(at))].sum() if len(at) else 0)
            sr = rc[i].sum() + (rt[rng.integers(0, len(rt), len(rt))].sum() if len(rt) else 0)
            reps[k] = (sa / na) / (sr / nr) if sr > 0 else np.inf
        lo, hi = np.percentile(reps, 2.5), np.percentile(reps, 97.5)
        out['%s c=%d' % (pt, c)] = dict(ber_pt=ber_a, uses_pt=na, ber_ref=ber_r, uses_ref=nr, ratio=ber_a / ber_r, lo=lo, hi=hi)
        print('%s c=%d: PT BER %.3g (%d uses)  (i) %.3g (%d uses)  ratio %.3g [%.3g, %.3g]' % (pt, c, ber_a, na, ber_r, nr, ber_a / ber_r, lo, hi))
json.dump(out, open(os.path.join(ROOT, 'a512_supp_fullref.json'), 'w'), indent=1)
