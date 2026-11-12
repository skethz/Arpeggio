#!/usr/bin/env python3
"""Parameter selection on a declared tuning set (seeds >= 1000; the held-out evaluation uses seeds < 1000).
Anechoic: a grid over (t0, t1, q, kappa) at fixed S and Na. CIM: the unpublished noise amplitude As and the pump-time
interpretation (step index vs. normalised time), chosen to give the baseline its best BER. Objective: total bit errors
over the listed SNRs (one shared set of channel draws per SNR). One JSON line per candidate to OUT.jsonl.
Usage: tune.py --nt 16 --nr 16 --M 4 --snrs 10,12 --n 2000 --na 64 --which ane|cim --out PREFIX [--S 128]"""
import argparse
import itertools
import json
import math

import torch

import mimo

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--nr', type=int, required=True)
ap.add_argument('--M', type=int, required=True)
ap.add_argument('--rho', type=float, default=0.0)
ap.add_argument('--snrs', required=True)
ap.add_argument('--n', type=int, default=2000)
ap.add_argument('--na', type=int, default=64)
ap.add_argument('--S', type=int, default=128)
ap.add_argument('--which', required=True)
ap.add_argument('--grid', default='')
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
D = 2 * a.nt
batches = []
for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
    g = torch.Generator(device='cuda'); g.manual_seed(1000 * 1_000_003 + si * 10_007)   # tuning seed 1000
    b = mimo.make_batch(a.n, a.nt, a.nr, a.M, snr, g, rho=a.rho)
    z, Ai, el2 = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    batches.append((snr, b, lm, mimo.ising(b, z)))
if a.which == 'ane':
    grid = json.loads(a.grid) if a.grid else dict(t0=[0.5, 1, 2, 4], t1=[0.02, 0.05, 0.1], q=[0, 0.25, 0.5, 1], kappa=[0, 0.2, 0.4])
    cands = [dict(S=a.S, t0=t0, t1=t1, q=q, kappa=k, lam=lm) for t0, t1, q, k, lm in
             itertools.product(grid['t0'], grid['t1'], grid['q'], grid.get('kappa', [0.0]), grid.get('lam', [0.0]))
             if t1 <= t0 and not (k > 0 and lm > 0)]
else:
    grid = json.loads(a.grid) if a.grid else dict(As=[1, 2, 5, 10, 20, 50, 100], pump=['step', 'time'])
    cands = [dict(As=A, pump=p) for A, p in itertools.product(grid['As'], grid['pump'])]
fo = open(a.out + '.jsonl', 'a')
for c in cands:
    gs = torch.Generator(device='cuda'); gs.manual_seed(1000 + 7919)
    err, bits, per = 0, 0, {}
    for snr, b, lm, I in batches:
        if a.which == 'ane':
            S_ = mimo.anechoic(I, a.na, c['S'], c['t0'], c['t1'], c['q'], kappa=c['kappa'], lam=c['lam'], gen=gs)
        else:
            S_ = mimo.cim(I, a.na, As=c['As'], gen=gs, pump=c['pump'])
        lh, _, _ = mimo.select(b, mimo.spins_to_levels(S_, a.M, D), lm)
        e, n = mimo.bit_errors(b, lh)
        err += e; bits += n; per[str(snr)] = e / n
    r = dict(which=a.which, nt=a.nt, nr=a.nr, M=a.M, rho=a.rho, na=a.na, cand=c, err=err, bits=bits, ber=err / bits, per_snr=per)
    fo.write(json.dumps(r) + '\n'); fo.flush()
    print(json.dumps(r), flush=True)
