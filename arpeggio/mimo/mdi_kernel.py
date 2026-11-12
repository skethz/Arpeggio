#!/usr/bin/env python3
"""MDI-Anechoic with the custom kernel as the solver (development check, not a frozen cohort): the same MDI wrapper
(mimo.mdi) with each sub-problem (guess, K) solved by the kernel (fixed point, Philox; 2K phases), against the float
MDI-Anechoic on the same draws; BER and development throughput on a shared GPU.
Usage: mdi_kernel.py CUBIN OUT.jsonl"""
import json
import sys
import time

import torch

import anefx
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
kern = anefx.Kernel(sys.argv[1])
fo = open(sys.argv[2], 'a')
MA = dict(Sk=128, t0=0.3, t1=0.3, q=0.4, kappa=0.0)
for nt, snrs, Ns, n in ((16, (18.0, 20.0, 22.0), 64, 4000), (16, (20.0,), 8, 4000)):
    for si, snr in enumerate(snrs):
        g = torch.Generator(device='cuda'); g.manual_seed(7 * 1_000_003 + si * 10_007 + Ns)
        b = mimo.make_batch(n, nt, nt, 16, snr, g)
        z, Ai, _ = mimo.mmse(b)
        calls = [0]

        def ksolver(I, na, K):
            calls[0] += 1
            F = anefx.to_fixed(I, MA['Sk'] * 2 * K, MA['t0'], MA['t1'], MA['q'], MA['kappa'])
            s8, _ = kern.anechoic(F, na, 7_000_000 + 1000 * calls[0], P=2 * K, mode='chains')
            return s8.float()
        gs = torch.Generator(device='cuda'); gs.manual_seed(7 * 1_000_003 + si * 10_007 + Ns + 7919)
        fsolver = lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, MA['t0'], MA['t1'], MA['q'], gen=gs, phases=2 * K)
        for impl, solver in (('kernel', ksolver), ('float', fsolver)):
            st = {}
            torch.cuda.synchronize(); t0 = time.time()
            lh = mimo.mdi(b, solver, Ns, 3, 8, z_mmse=z, stats=st)
            torch.cuda.synchronize(); dt = time.time() - t0
            e, nb = mimo.bit_errors(b, lh)
            r = dict(nt=nt, M=16, snr=snr, Ns=Ns, impl=impl, n=n, seed=7, ber=e / nb, err=e, seconds=dt, det_per_s=n / dt,
                     mean_anneals=st['anneals'] / n, mdiane=MA)
            fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)
