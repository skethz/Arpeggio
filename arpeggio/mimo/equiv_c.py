#!/usr/bin/env python3
"""BER equivalence of the kernel solvers with the PyTorch solvers inside the MDI wrapper (milestone C), held-out seed 21,
same channel draws for all four; MDI settings as published (Table I / DI-MIMO), Ns as given.
Usage: equiv_c.py ANE_CUBIN AHC_CUBIN OUT.jsonl"""
import json
import sys
import time

import torch

import ahcfx
import anefx
import mdi_solvers as ms
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
ka = anefx.Kernel(sys.argv[1]); kh = ahcfx.AhcKernel(sys.argv[2])
fo = open(sys.argv[3], 'a')
for shape, nt, M, snr, Ns, n, B in (('16x16', 16, 16, 20.0, 64, 4000, 2000), ('32x32', 32, 4, 14.0, 64, 8000, 4000)):
    cfg = ms.MDI[(shape, M)]
    acc = {impl: [0, 0, 0.0] for impl in ('ahc_torch', 'ahc_kernel', 'ane_torch', 'ane_kernel')}
    for bi in range(n // B):
        g = torch.Generator(device='cuda'); g.manual_seed(21 * 1_000_003 + bi)
        b = mimo.make_batch(B, nt, nt, M, snr, g)
        z, Ai, _ = mimo.mmse(b)
        for impl in acc:
            gs = torch.Generator(device='cuda'); gs.manual_seed(21 * 1_000_003 + bi + 7919)
            sol = ms.make_solver(impl, gs, ka, kh, seed0=21_000_000 + bi * 100_000)
            torch.cuda.synchronize(); t0 = time.time()
            lh, st = ms.detect(b, impl, Ns, cfg, sol, z=z)
            torch.cuda.synchronize(); acc[impl][2] += time.time() - t0
            e, nb = mimo.bit_errors(b, lh); acc[impl][0] += e; acc[impl][1] += nb
    for impl, (e, nb, t) in acc.items():
        r = dict(shape=shape, M=M, snr=snr, Ns=Ns, impl=impl, n=n, seed=21, err=e, bits=nb, ber=e / nb, seconds=t)
        fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)
