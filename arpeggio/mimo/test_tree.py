#!/usr/bin/env python3
"""kbest2 (milestone B) returns the same decisions as milestone A's kbest on random problems (QPSK and 16-QAM,
several shapes and K); and the sphere decoder equals exhaustive ML on 3x3 16-QAM."""
import itertools
import sys
import time

import numpy as np
import torch

import mimo
import tree

ok = True
g = torch.Generator(device='cuda'); g.manual_seed(31)
for (nt, nr, M, snr, K) in [(16, 16, 4, 8.0, 1), (16, 16, 4, 8.0, 32), (16, 16, 16, 18.0, 8), (32, 64, 16, 10.0, 64),
                            (64, 64, 4, 12.0, 16), (16, 128, 16, 5.0, 4)]:
    b = mimo.make_batch(400, nt, nr, M, snr, g)
    Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
    lv = np.array(mimo.PAM[M]['levels'], np.float64)
    t0 = time.time(); a1 = tree.kbest(Hn, yn, lv, K)[0][:, 0, :]; t1 = time.time()
    a2, _ = tree.kbest2(Hn, yn, lv, K); t2 = time.time()
    same = np.array_equal(a1, a2)
    ok &= same
    print('%s kbest2 == kbest %dx%d M%d K%d (%.2fs vs %.2fs, incl. compile)' % ('PASS' if same else 'FAIL', nt, nr, M, K,
                                                                               t1 - t0, t2 - t1), flush=True)
b = mimo.make_batch(300, 3, 3, 16, 12.0, g)
allx = np.array(list(itertools.product(mimo.PAM[16]['levels'], repeat=6)), np.float64)
Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
xs, nodes, done = tree.sphere_decoder(Hn, yn, np.array(mimo.PAM[16]['levels'], np.float64), 2_000_000)
d = ((yn[:, None, :] - np.einsum('bij,kj->bki', Hn, allx)) ** 2).sum(-1)
ml = allx[d.argmin(1)]
same = np.array_equal(ml, xs) and done.all()
ok &= same
print('%s sphere decoder == exhaustive ML (3x3 16-QAM, 300 instances, mean nodes %.0f)' % ('PASS' if same else 'FAIL', nodes.mean()))
sys.exit(0 if ok else 1)
