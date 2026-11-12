#!/usr/bin/env python3
"""Anechoic on Princeton's delta formulation (dDI, K = 1) with alternating copy updates (phases = 2), tuning set
(seed 1000). Grid over S, t0, t1, q, kappa, lam; AHC-dDI on the same draws for reference. JSON lines to OUT.jsonl.
Usage: tune_ddi.py --nt 16 --M 16 --snrs 20,24 --n 2000 --na 64 --grid JSON --out PREFIX"""
import argparse
import itertools
import json

import torch

import mimo

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--M', type=int, default=16)
ap.add_argument('--snrs', required=True)
ap.add_argument('--n', type=int, default=2000)
ap.add_argument('--na', type=int, default=64)
ap.add_argument('--grid', required=True)
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
B = []
for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
    g = torch.Generator(device='cuda'); g.manual_seed(1000 * 1_000_003 + si * 10_007)
    b = mimo.make_batch(a.n, a.nt, a.nt, a.M, snr, g); z, Ai, el2 = mimo.mmse(b); lm = mimo.mmse_hard(b, z, Ai)
    B.append((b, lm, mimo.ising_delta(b, z, K=1)))
G = json.loads(a.grid)
fo = open(a.out + '.jsonl', 'a')


def ber(fn):
    err = bits = 0
    for b, lm, Id in B:
        gs = torch.Generator(device='cuda'); gs.manual_seed(1000 + 7919)
        lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(fn(Id, gs), Id, a.M), lm)
        e, n = mimo.bit_errors(b, lh); err += e; bits += n
    return err / bits


r = dict(method='ahc-dDI', na=a.na, ber=ber(lambda Id, gs: mimo.ahc(Id, a.na, gen=gs)))
fo.write(json.dumps(r) + '\n'); print(json.dumps(r), flush=True)
for S, t0, t1, q, k, lm_ in itertools.product(G['S'], G['t0'], G['t1'], G['q'], G.get('kappa', [0]), G.get('lam', [0])):
    if t1 > t0 or (k > 0 and lm_ > 0):
        continue
    c = dict(S=S, t0=t0, t1=t1, q=q, kappa=k, lam=lm_, phases=2)
    r = dict(method='ane-dDI', na=a.na, nt=a.nt, cand=c,
             ber=ber(lambda Id, gs: mimo.anechoic(Id, a.na, S, t0, t1, q, kappa=k, lam=lm_, gen=gs, phases=2)))
    fo.write(json.dumps(r) + '\n'); fo.flush()
