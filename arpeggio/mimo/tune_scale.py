#!/usr/bin/env python3
"""Anechoic schedules (usage: tune_scale.py CUBIN OUT.jsonl [round2|ddi_qpsk]) for the milestone-B shapes on the tuning set (seed 1000), i.i.d. channels only (reused for
rho = 0.5): S fixed (128 steps RI; 256 half-steps dDI, i.e. 128 updates per spin), 16 anneals, the custom kernel;
grid over (t0, t1) and q at one SNR per configuration (K-best 32's 1e-3 point from the pre-scan, rounded).
Output: one JSON line per (configuration, schedule) and the best per configuration."""
import json
import sys

import torch

import anefx
import fxdetect
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
kern = anefx.Kernel(sys.argv[1])
fo = open(sys.argv[2], 'a')
CFG = [(64, 64, 4, 13.0), (16, 64, 4, 4.0), (16, 128, 4, 1.0), (32, 64, 4, 7.0), (32, 128, 4, 4.0),
       (64, 64, 16, 23.0), (16, 64, 16, 11.0), (16, 128, 16, 8.0), (32, 64, 16, 14.0), (32, 128, 16, 10.5)]
TT = [(0.2, 0.2), (0.3, 0.3), (0.45, 0.45), (0.6, 0.6), (0.8, 0.8), (0.8, 0.3), (0.6, 0.2)]
QQ = [0.25, 0.4, 0.6, 0.8]
KIND = None
if len(sys.argv) > 3 and sys.argv[3] == 'ddi_qpsk':  # QPSK in Princeton's delta formulation (DI-MIMO), round-2 grid
    CFG = [c for c in CFG if c[2] == 4]
    KIND = 'ddi'
if len(sys.argv) > 3 and sys.argv[3] in ('round2', 'ddi_qpsk'):   # round 2: round 1's bests at the grid edges (t 0.2, q 0.8)
    TT = TT + [(0.1, 0.1), (0.15, 0.15), (1.0, 1.0), (1.2, 1.2)]
    QQ = QQ + [1.0, 1.2, 1.6, 2.0]
for nt, nr, M, snr in CFG:
    bits = 2 * nt * mimo.PAM[M]['bits']
    n = int(2e5 / bits)
    g = torch.Generator(device='cuda'); g.manual_seed(1000 * 1_000_003 + nt * 31 + nr)
    b = mimo.make_batch(n, nt, nr, M, snr, g)
    z, Ai, _ = mimo.mmse(b)
    best = None
    for t0, t1 in TT:
        for q in QQ:
            kind = KIND or ('ri' if M == 4 else 'ddi')
            sc = dict(kind=kind, Nt=nt, Nr=nr, M=M, S=128 if kind == 'ri' else 256, t0=t0, t1=t1, q=q, kappa=0.0)
            lh = fxdetect.detect(b, sc, 16, kern, seed=1000 * 7919 + nt + nr, z=z, Ai=Ai)
            e, nb = mimo.bit_errors(b, lh)
            r = dict(nt=nt, nr=nr, M=M, snr=snr, n=n, anneals=16, sched=sc, ber=e / nb, err=e)
            fo.write(json.dumps(r) + '\n'); fo.flush()
            if best is None or e < best['err']:
                best = r
    e, nb = mimo.bit_errors(b, mimo.mmse_hard(b, z, Ai))
    print(json.dumps(dict(best=best, mmse_ber=e / nb)), flush=True)
    fo.write(json.dumps(dict(best=best, mmse_ber=e / nb)) + '\n'); fo.flush()
