#!/usr/bin/env python3
"""A5.6 amendment 6 (STATUS.md, author 6 Nov 2026: "Queue it"): K-best (Guo & Nilsson 2006, apx.detect 'kbest<K>', tree.kbest2,
numba CPU, the path of every saved K-best run) on the draws of Table IV's row "D128 X64": 64x64 16-QAM, 22 dB, seed 344, batches
of 500 (apx.draw, the draws of X3P x64, X64F and X64S). CPU only. Stop as X3: after the batch that reaches --min-vec erroneous uses,
or at --batches. Writes ROOT/X64K/x64/kbest<K>/snr_22.00/bNNNNN.npz (biterr per use); resumes; done.json at the end.
Usage: x64_kbest.py ROOT --K 128 [--batches 600] [--min-vec 2000] [--seed 344] [--snr 22] [--B 500]"""
import argparse
import json
import os
import time

import numpy as np
import torch

import apx

ap = argparse.ArgumentParser()
ap.add_argument('root')
ap.add_argument('--K', type=int, required=True)
ap.add_argument('--batches', type=int, default=600)
ap.add_argument('--min-vec', type=int, default=2000)
ap.add_argument('--seed', type=int, default=344)
ap.add_argument('--snr', type=float, default=22.0)
ap.add_argument('--B', type=int, default=500)
a = ap.parse_args()
m = 'kbest%d' % a.K
d = os.path.join(a.root, 'X64K', 'x64', m, 'snr_%05.2f' % a.snr)
os.makedirs(d, exist_ok=True)
n = ve = be = 0
for bi in range(a.batches):
    f = os.path.join(d, 'b%05d.npz' % bi)
    if not os.path.exists(f):
        t0 = time.time()
        b = apx.draw(a.seed, a.snr, bi, a.B, 64, 16, dev='cpu')
        with torch.no_grad():
            lh, _, _ = apx.detect(m, b, 'x64', None, None)
        bev = apx.biterr_per_use(b, lh)
        info = dict(method=m, seed=a.seed, snr=a.snr, bi=bi, m=a.B, N0=b['N0'], host='hostB', cpu=True, seconds_untimed=time.time() - t0)
        tmp = os.path.join(d, '.tmp_b%05d.npz' % bi)
        np.savez_compressed(tmp, biterr=bev.cpu().numpy().astype(np.uint8), info=np.array(json.dumps(info)))
        os.rename(tmp, f)
        print(time.strftime('%m-%d %H:%M:%S'), m, 'batch', bi, '%.1f s' % info['seconds_untimed'], flush=True)
    x = np.load(f, allow_pickle=False)['biterr']
    n += len(x); ve += int((x > 0).sum()); be += int(x.sum())
    if ve >= a.min_vec:
        break
json.dump(dict(method=m, uses=n, vec_err=ve, bit_err=be, ber=be / (n * 256), batches=bi + 1, seed=a.seed, snr=a.snr, t=time.time()),
          open(os.path.join(d, 'done.json'), 'w'))
print('DONE', m, n, ve, be, flush=True)
