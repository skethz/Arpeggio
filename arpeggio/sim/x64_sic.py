#!/usr/bin/env python3
"""A5.6 amendment 5 (STATUS.md): MMSE-SIC (mimo.mmse_sic, per='real', the paper's baseline and MDI's own SIC guess) on the draws of
Table IV's row "D128 X64": 64x64 16-QAM, 22 dB, seed 344, batches of 500 (apx.draw, the draws x3_prod.py used). Writes
ROOT/X64S/x64/mmse_sic/snr_22.00/bNNNNN.npz (biterr per use); resumes; done.json at the end.
Usage: x64_sic.py ROOT [--batches 600] [--seed 344] [--snr 22] [--B 500]"""
import argparse
import json
import os
import time

import numpy as np
import torch

import apx

ap = argparse.ArgumentParser()
ap.add_argument('root')
ap.add_argument('--batches', type=int, default=600)
ap.add_argument('--seed', type=int, default=344)
ap.add_argument('--snr', type=float, default=22.0)
ap.add_argument('--B', type=int, default=500)
a = ap.parse_args()
d = os.path.join(a.root, 'X64S', 'x64', 'mmse_sic', 'snr_%05.2f' % a.snr)
os.makedirs(d, exist_ok=True)
n = ve = be = 0
for bi in range(a.batches):
    f = os.path.join(d, 'b%05d.npz' % bi)
    if not os.path.exists(f):
        t0 = time.time()
        b = apx.draw(a.seed, a.snr, bi, a.B, 64, 16)
        with torch.no_grad():
            lh = apx.mimo.mmse_sic(b, per='real')
        bev = apx.biterr_per_use(b, lh)
        info = dict(method='mmse_sic', per='real', seed=a.seed, snr=a.snr, bi=bi, m=a.B, N0=b['N0'], gpu=torch.cuda.get_device_name(0), seconds_untimed=time.time() - t0)
        tmp = os.path.join(d, '.tmp_b%05d.npz' % bi)
        np.savez_compressed(tmp, biterr=bev.cpu().numpy().astype(np.uint8), info=np.array(json.dumps(info)))
        os.rename(tmp, f)
        print(time.strftime('%m-%d %H:%M:%S'), 'sic batch', bi, '%.1f s' % info['seconds_untimed'], flush=True)
    x = np.load(f, allow_pickle=False)['biterr']
    n += len(x); ve += int((x > 0).sum()); be += int(x.sum())
json.dump(dict(uses=n, vec_err=ve, bit_err=be, ber=be / (n * 256), batches=a.batches, seed=a.seed, snr=a.snr, t=time.time()), open(os.path.join(d, 'done.json'), 'w'))
print('DONE sic', n, ve, be, flush=True)
