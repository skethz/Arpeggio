#!/usr/bin/env python3
"""Validation of the PIMI reproduction against the authors' Fig. 6 (milestone D), two ways, one JSON line per point:
- source 'their_instances': our PIMI (pimi.pimi_torch, PyTorch generators) on the authors' own 10,000 DI-MIMO instances
  per Eb/N0 (Zenodo archives, cached by pimi_zen.py), with their MMSE estimates and true symbols; their report.json
  BER on the same instances is the reference (only the solver's random numbers differ);
- source 'our_generator': the whole chain on fresh instances from our port of their channel model
  (pimi.make_batch_pimi, Eb/N0 per bit, per-instance received power), our port of their MMSE and mapping.
Schedule per panel: pimi.sched_for (the one of their two that reproduces their report; --sched overrides).
Settings: Table I hardware steps and the 4x 'theoretical optimal' steps (32 trials), plus the 2x steps that two
report.json files name for their 4x folders (16x16 4-QAM, 8x8 64-QAM).
Usage: run_pimi_fig6.py --cache DIR --out PREFIX [--sources their_instances,our_generator] [--panels 16x16_16,...]"""
import argparse
import glob
import json
import os
import re
import time

import numpy as np
import torch

import pimi

ap = argparse.ArgumentParser()
ap.add_argument('--cache', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--sources', default='their_instances,our_generator')
ap.add_argument('--panels', default='')
ap.add_argument('--batch', type=int, default=2500)
ap.add_argument('--seed', type=int, default=44)
ap.add_argument('--sched', default='')
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
HW = {(8, 4): 16, (8, 16): 32, (8, 64): 64, (16, 4): 32, (16, 16): 64, (16, 64): 64}       # Table I
EXTRA = {(16, 4): [64], (8, 64): [128]}                                                      # report.json num_steps
fo = open(a.out + '.jsonl', 'a')
panels = set(x for x in a.panels.split(',') if x)


def emit(r):
    fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)


def settings(nt, M):
    return [HW[(nt, M)], 4 * HW[(nt, M)]] + EXTRA.get((nt, M), [])


files = sorted(glob.glob(os.path.join(a.cache, 'nt*_M*_snr*.npz')))
for f in files:
    nt, M, snr = map(int, re.search(r'nt(\d+)_M(\d+)_snr(\d+)', f).groups())
    if panels and '%dx%d_%d' % (nt, nt, M) not in panels:
        continue
    pid = nt * 1000 + M * 10 + snr
    sname = a.sched or pimi.sched_name(nt, M)
    beta, gamma = pimi.SCHED[sname]
    if 'their_instances' in a.sources:
        z = np.load(f)
        Jq = torch.tensor(z['Jq'].astype(np.int32), device='cuda')
        hq = torch.tensor(z['hq'].astype(np.int32), device='cuda')
        xt = torch.tensor(z['xt'], dtype=torch.float32, device='cuda')
        xm = torch.tensor(z['xm'], dtype=torch.float32, device='cuda')
        n = xt.shape[0]
        em, nbits = pimi.bit_errors(xt, xm, M)
        for steps in settings(nt, M):
            g = torch.Generator(device='cuda'); g.manual_seed(a.seed * 1_000_003 + pid * 7 + steps)
            err = 0
            torch.cuda.synchronize(); t0 = time.time()
            for i in range(0, n, a.batch):
                P = dict(Jq=Jq[i:i + a.batch], hq=hq[i:i + a.batch], xm=xm[i:i + a.batch])
                S, E2 = pimi.pimi_torch(P, steps, pimi.TRIALS, g, beta=beta, gamma=gamma)
                lh = pimi.decide(P, pimi.select(P, S, E2), M)
                err += pimi.bit_errors(xt[i:i + a.batch], lh, M)[0]
            torch.cuda.synchronize()
            emit(dict(source='their_instances', nt=nt, M=M, ebn0=snr, snr_ours=pimi.ebn0_to_snr(snr, M), steps=steps,
                      trials=pimi.TRIALS, n=n, err=err, bits=nbits, ber=err / nbits, ber_mmse=em / nbits,
                      seconds=time.time() - t0, seed=a.seed, schedule=sname))
    if 'our_generator' in a.sources:
        n = 10000
        for steps in settings(nt, M):
            g = torch.Generator(device='cuda'); g.manual_seed(a.seed * 1_000_003 + pid)       # same draws per setting
            gs = torch.Generator(device='cuda'); gs.manual_seed(a.seed * 1_000_003 + pid + 7919 + steps)
            err = errm = nbits = 0
            torch.cuda.synchronize(); t0 = time.time()
            for i in range(0, n, a.batch):
                b = pimi.make_batch_pimi(min(a.batch, n - i), nt, nt, M, float(snr), g)
                xm = pimi.slice_levels(pimi.mmse_z(b), M)
                P = pimi.problem(b, xm)
                S, E2 = pimi.pimi_torch(P, steps, pimi.TRIALS, gs, beta=beta, gamma=gamma)
                lh = pimi.decide(P, pimi.select(P, S, E2), M)
                e, nb_ = pimi.bit_errors(b['l'], lh, M)
                err += e; nbits += nb_; errm += pimi.bit_errors(b['l'], xm, M)[0]
            torch.cuda.synchronize()
            emit(dict(source='our_generator', nt=nt, M=M, ebn0=snr, snr_ours=pimi.ebn0_to_snr(snr, M), steps=steps,
                      trials=pimi.TRIALS, n=n, err=err, bits=nbits, ber=err / nbits, ber_mmse=errm / nbits,
                      seconds=time.time() - t0, seed=a.seed, schedule=sname))
