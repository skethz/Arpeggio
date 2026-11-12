#!/usr/bin/env python3
"""Scaling pre-scan on the tuning set (seed 1000): BER of MMSE, MMSE-SIC and K-best 32 on a coarse SNR grid for every
milestone-B configuration, to place the held-out grids. One JSON line per (config, SNR, method)."""
import json
import sys

import numpy as np
import torch

import mimo
import tree

torch.backends.cuda.matmul.allow_tf32 = False
fo = open(sys.argv[1], 'a')
SHAPES = [(64, 64), (16, 64), (16, 128), (32, 64), (32, 128)]
for M in (4, 16):
    for rho in (0.0, 0.5):
        for nt, nr in SHAPES:
            bits = 2 * nt * mimo.PAM[M]['bits']
            n = max(500, int(1e5 / bits))
            grid = range(-8, 22, 2) if M == 4 else range(0, 32, 2)
            for si, snr in enumerate(grid):
                g = torch.Generator(device='cuda'); g.manual_seed(1000 * 1_000_003 + si * 10_007 + nt * 7 + nr + int(rho * 10))
                b = mimo.make_batch(n, nt, nr, M, float(snr), g, rho=rho)
                z, Ai, _ = mimo.mmse(b)
                res = {'mmse': mimo.mmse_hard(b, z, Ai), 'sic': mimo.mmse_sic(b, 'real')}
                Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
                res['kbest32'] = torch.tensor(tree.kbest2(Hn, yn, np.array(mimo.PAM[M]['levels'], np.float64), 32)[0],
                                              device='cuda', dtype=torch.float32)
                out = {}
                for k, lh in res.items():
                    e, nb = mimo.bit_errors(b, lh); out[k] = e / nb
                    fo.write(json.dumps(dict(nt=nt, nr=nr, M=M, rho=rho, snr=snr, method=k, n=n, ber=e / nb, err=e)) + '\n')
                fo.flush()
                print(nt, nr, M, rho, snr, ' '.join('%s %.2e' % kv for kv in out.items()), flush=True)
                if out['mmse'] < 2e-5:
                    break
