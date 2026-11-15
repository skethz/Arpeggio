#!/usr/bin/env python3
"""A5.19 post-hoc check (15 Nov 2026, after the analysis; not in PROTOCOL_A519 section 7): A64 (the paper's B = 1 Arpeggio) over C64
(re-tuned Chord) at P4, on all 600 held-out batches of seed 2028. Same estimators as analyze_a519.py (a56an.boot_ratio, 4,000 replicates,
seed 12345; exact McNemar). Reported as post hoc, next to the pre-registered P2 analogue (A5.15 A32/C1).
Usage: posthoc_a64_c64.py ROOT OUT.json   (run from a519z with src/ on sys.path)"""
import glob, json, os, sys
import numpy as np
import a56an as AN

ROOT, OUT = sys.argv[1], sys.argv[2]
if os.path.exists(OUT):
    sys.exit('refusing: exists')
A64, C64, SNR = 'abl_far_64_0.1_0.1_0_bal_8', 'abl_ape_0.2_0.2_0.2_rand_8', 22.0


def arm(m):
    out = {}
    for d in sorted(glob.glob(os.path.join(ROOT, 'h4_c*', 'x64', m, 'snr_%05.2f' % SNR))):
        for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
            bi = int(os.path.basename(f)[1:6])
            z = np.load(f, allow_pickle=False)
            info = json.loads(str(z['info']))
            assert int(info['bi']) == bi and info['method'] == m
            out[bi] = z['biterr'].astype(np.int64)
    return out


a, b = arm(A64), arm(C64)
idx = sorted(set(a) & set(b))
x = np.concatenate([a[i] for i in idx]); y = np.concatenate([b[i] for i in idx])
r, lo, hi = AN.boot_ratio(x, y)
p, nx, ny = AN.mcnemar(x, y)
res = dict(note='post hoc, after the A5.19 analysis; A64/C64 at P4, seed 2028', ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny,
           uses=int(len(x)), batches=len(idx), a_bit=int(x.sum()), b_bit=int(y.sum()),
           term='Chord leads' if lo > 1 else ('Arpeggio leads' if hi < 1 else 'no detected difference'))
json.dump(res, open(OUT, 'w'), indent=1)
print('A64/C64 %.4f [%.4f, %.4f] p=%.2g uses=%d bits %d/%d %s' % (r, lo, hi, p, res['uses'], res['a_bit'], res['b_bit'], res['term']))
