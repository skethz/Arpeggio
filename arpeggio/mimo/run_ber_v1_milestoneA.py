#!/usr/bin/env python3
"""Uncoded BER of several detectors on the same channel draws. One JSON line per (method, SNR) to OUT.jsonl.
Usage: run_ber.py --nt 16 --nr 16 --M 16 [--rho 0] --snrs 10,14,18 --n 20000 --batch 2000 --seed 1 --out PREFIX
       --methods mmse,sd,kbest32,cim64,ane64 [--ane '{"S":128,"t0":..,"t1":..,"q":..,"kappa":..}'] [--cim-as 10]
Seeds: channel draws come from a torch generator seeded with (seed, SNR index, batch index); the solvers' random
numbers from a separate generator seeded with seed + 7919."""
import argparse
import json
import math
import time

import numpy as np
import torch

import mimo
import tree

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--nr', type=int, required=True)
ap.add_argument('--M', type=int, required=True)
ap.add_argument('--rho', type=float, default=0.0)
ap.add_argument('--snrs', required=True)
ap.add_argument('--n', type=int, required=True)
ap.add_argument('--batch', type=int, default=2000)
ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--methods', required=True)
ap.add_argument('--ane', default='{"S":128,"t0":2.0,"t1":0.05,"q":0.5,"kappa":0.3}')
ap.add_argument('--aned', default='{"S":256,"t0":0.2,"t1":0.1,"q":0.2,"phases":2}')
ap.add_argument('--cim-as', type=float, default=10.0)
ap.add_argument('--cim-pump', default='step')
ap.add_argument('--sd-cap', type=int, default=2_000_000)
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
methods = a.methods.split(',')
ane = json.loads(a.ane)
aned = json.loads(a.aned)
levels = np.array(mimo.PAM[a.M]['levels'], np.float64)
D = 2 * a.nt
fo = open(a.out + '.jsonl', 'a')
for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
    acc = {m: dict(err=0, bits=0, t=0.0, extra=0) for m in methods}
    nb = math.ceil(a.n / a.batch)
    for bi in range(nb):
        B = min(a.batch, a.n - bi * a.batch)
        g = torch.Generator(device='cuda'); g.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi)
        gs = torch.Generator(device='cuda'); gs.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi + 7919)
        b = mimo.make_batch(B, a.nt, a.nr, a.M, snr, g, rho=a.rho)
        z, Ai, el2 = mimo.mmse(b)
        lm = mimo.mmse_hard(b, z, Ai)
        I = None
        for m in methods:
            torch.cuda.synchronize(); t0 = time.time()
            if m == 'mmse':
                lh = lm
            elif m == 'sd' or m.startswith('kbest'):
                Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
                if m == 'sd':
                    xh, nodes, done = tree.sphere_decoder(Hn, yn, levels, a.sd_cap)
                    acc[m]['extra'] += int((~done).sum())
                else:
                    K = int(m[5:])
                    lst, dd = tree.kbest(Hn, yn, levels, K)
                    xh = lst[:, 0, :]
                lh = torch.tensor(xh, device='cuda', dtype=torch.float32)
            elif m[3:4] == 'd':                                          # delta formulation (dDI, K = 1): aned / ahcd / cimd
                Id = mimo.ising_delta(b, z, K=1)
                na = int(m[4:])
                if m.startswith('aned'):
                    S_ = mimo.anechoic(Id, na, aned['S'], aned['t0'], aned['t1'], aned['q'], kappa=aned.get('kappa', 0.0),
                                       lam=aned.get('lam', 0.0), gen=gs, phases=aned.get('phases', 2))
                elif m.startswith('ahcd'):
                    S_ = mimo.ahc(Id, na, gen=gs)
                elif m.startswith('cimd'):
                    S_ = mimo.cim(Id, na, As=a.cim_as, gen=gs, pump=a.cim_pump)
                else:
                    raise SystemExit('unknown method ' + m)
                lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, a.M), lm)
            else:
                if I is None:
                    I = mimo.ising(b, z)
                if m.startswith('ahc'):
                    S_ = mimo.ahc(I, int(m[3:]), gen=gs)
                elif m.startswith('cim'):
                    S_ = mimo.cim(I, int(m[3:]), As=a.cim_as, gen=gs, pump=a.cim_pump)
                elif m.startswith('ane'):
                    S_ = mimo.anechoic(I, int(m[3:]), ane['S'], ane['t0'], ane['t1'], ane['q'], kappa=ane.get('kappa', 0.0),
                                       lam=ane.get('lam', 0.0), ramp=ane.get('ramp', True), gen=gs)
                else:
                    raise SystemExit('unknown method ' + m)
                lh, _, _ = mimo.select(b, mimo.spins_to_levels(S_, a.M, D), lm)
            torch.cuda.synchronize(); acc[m]['t'] += time.time() - t0
            e, n = mimo.bit_errors(b, lh)
            acc[m]['err'] += e; acc[m]['bits'] += n
    for m in methods:
        r = dict(nt=a.nt, nr=a.nr, M=a.M, rho=a.rho, snr=snr, method=m, n=a.n, seed=a.seed, err=acc[m]['err'],
                 bits=acc[m]['bits'], ber=acc[m]['err'] / acc[m]['bits'], seconds=acc[m]['t'])
        if m == 'sd':
            r['sd_unfinished'] = acc[m]['extra']
        if m.startswith('aned'):
            r['aned'] = aned
        elif m.startswith('ane'):
            r['ane'] = ane
        if m.startswith('cim'):
            r['cim_as'] = a.cim_as; r['cim_pump'] = a.cim_pump
        fo.write(json.dumps(r) + '\n'); fo.flush()
        print(json.dumps(r), flush=True)
