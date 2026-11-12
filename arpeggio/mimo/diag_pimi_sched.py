#!/usr/bin/env python3
"""Diagnostic (milestone D, not tuning): which of the two schedules present in the authors' code reproduces their own
published BER (report.json) on their own instances, per Fig. 6 panel. Candidates, both from their Zenodo code:
  A  16-QAM run notebooks (run_experiment_*.ipynb, 8x8 and 16x16): beta 2, gamma linspace(0.1, 0.999)
  B  BER_*/gen_noise.py (the FPGA noise-table generator): beta 1, gamma linspace(0.01, 0.999)
No 4-QAM or 64-QAM run notebook is published. Output: one JSON line per (panel, Eb/N0, steps, schedule).
Usage: diag_pimi_sched.py CACHE REPORTS.jsonl OUT.jsonl"""
import json
import math
import os
import re
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pimi  # noqa: E402

torch.backends.cuda.matmul.allow_tf32 = False
cache, rep_path, out = sys.argv[1:4]
SCHED = {'A': (2.0, (0.1, 0.999)), 'B': (1.0, (0.01, 0.999))}
PANELS = {(16, 4): (32, 64), (8, 4): (16, 64), (16, 64): (64, 256), (8, 64): (64, 128), (16, 16): (64, 256), (8, 16): (32, 128)}
DIRS = {(16, 4, 64): 128, (8, 64, 128): 256}                               # report folder of the 4x curve
rep = {}
for l in open(rep_path):
    r = json.loads(l)
    m = re.search(r'Nt(\d+)_Nr\d+_(\d+)QAM/(\d+)/tanh_lut_4/16_precision/(\d+)_steps_32_anneals', r['path'])
    if m:
        nt, M, snr, st = map(int, m.groups())
        rep[(nt, M, snr, st)] = r['report']
fo = open(out, 'a')
for (nt, M), steps in PANELS.items():
    for snr in sorted({k[2] for k in rep if k[:2] == (nt, M)}):
        f = os.path.join(cache, 'nt%d_M%d_snr%d.npz' % (nt, M, snr))
        if not os.path.exists(f):
            continue
        z = np.load(f)
        Jq = torch.tensor(z['Jq'].astype(np.int32), device='cuda'); hq = torch.tensor(z['hq'].astype(np.int32), device='cuda')
        xt = torch.tensor(z['xt'], dtype=torch.float32, device='cuda'); xm = torch.tensor(z['xm'], dtype=torch.float32, device='cuda')
        for st in steps:
            t = rep.get((nt, M, snr, DIRS.get((nt, M, st), st)))
            if t is None:
                continue
            for name, (beta, gamma) in SCHED.items():
                g = torch.Generator(device='cuda'); g.manual_seed(45 * 1_000_003 + nt * 1000 + M * 10 + snr + st)
                err = 0
                for i in range(0, xt.shape[0], 2500):
                    P = dict(Jq=Jq[i:i + 2500], hq=hq[i:i + 2500], xm=xm[i:i + 2500])
                    S, E2 = pimi.pimi_torch(P, st, 32, g, beta=beta, gamma=gamma)
                    err += pimi.bit_errors(xt[i:i + 2500], pimi.decide(P, pimi.select(P, S, E2), M), M)[0]
                nbits = xt.numel() * pimi.nbits(M)
                se = t['ber_std'] / math.sqrt(t['num_samples']) * math.sqrt(2)
                r = dict(nt=nt, M=M, ebn0=snr, steps=st, schedule=name, beta=beta, gamma=gamma, ber=err / nbits,
                         ber_report=t['ber'], z=(err / nbits - t['ber']) / se if se > 0 else None)
                fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)
