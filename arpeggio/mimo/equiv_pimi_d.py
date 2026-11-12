#!/usr/bin/env python3
"""BER equivalence of the PIMI kernel (Philox + inverse-CDF noise, bit-exact with pimi.pimi_fx) and the PyTorch PIMI
(torch.randn / torch.randint noise) on the same channel draws (milestone D; seed 46, not a held-out comparison seed):
the two differ only in their random-number source. Usage: equiv_pimi_d.py CUBIN OUT.jsonl"""
import json
import sys
import time

import torch

import mimo
import pimi

torch.backends.cuda.matmul.allow_tf32 = False
kern = pimi.PimiKernel(sys.argv[1])
fo = open(sys.argv[2], 'a')
CASES = [(16, 16, 20.0 + 6.0206, 64), (16, 16, 25.0 + 6.0206, 64), (16, 16, 25.0 + 6.0206, 256), (8, 16, 25.0 + 6.0206, 32),
         (32, 4, 14.0, 64), (32, 16, 22.0, 128), (16, 4, 13.0103, 32)]
n, B = 64000, 4000
for ci, (nt, M, snr, steps) in enumerate(CASES):
    acc = {'torch': [0, 0, 0.0], 'kernel': [0, 0, 0.0]}
    for bi in range(n // B):
        g = torch.Generator(device='cuda'); g.manual_seed(46 * 1_000_003 + ci * 10_007 + bi)
        b = mimo.make_batch(B, nt, nt, M, snr, g)
        z = pimi.mmse_z(b)
        gs = torch.Generator(device='cuda'); gs.manual_seed(46 * 1_000_003 + ci * 10_007 + bi + 7919)
        for impl in ('torch', 'kernel'):
            torch.cuda.synchronize(); t0 = time.time()
            if impl == 'torch':
                lh = pimi.detect_torch(b, steps, pimi.TRIALS, gs, z=z)
            else:
                lh = pimi.detect_kernel(b, kern, steps, pimi.TRIALS, 46_000_000 + 1000 * (ci * 1000 + bi), z=z,
                                        warps=4 if nt == 8 else 8)
            torch.cuda.synchronize(); acc[impl][2] += time.time() - t0
            e, nb = mimo.bit_errors(b, lh)
            acc[impl][0] += e; acc[impl][1] += nb
    r = dict(nt=nt, M=M, snr=snr, steps=steps, n=n, seed=46, schedule=pimi.sched_name(nt, M),
             ber_torch=acc['torch'][0] / acc['torch'][1], ber_kernel=acc['kernel'][0] / acc['kernel'][1],
             err_torch=acc['torch'][0], err_kernel=acc['kernel'][0], ratio=(acc['kernel'][0] / max(1, acc['torch'][0])),
             s_torch=acc['torch'][2], s_kernel=acc['kernel'][2])
    fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)
