#!/usr/bin/env python3
"""Detection with the custom kernel (DESIGN.md B3), and the BER-equivalence check against the float reference.
detect(): MMSE -> Ising mapping (RI-MIMO, or dDI K = 1 around the MMSE estimate) -> fixed point -> kernel (best
anneal per instance) -> levels -> the lower ||y - Hx||^2 of that candidate and MMSE.
Usage (equivalence): fxdetect.py --cubin C --out PREFIX --cfg q16|x16|... --snrs ... --n N --seed 1 --anneals 16,64"""
import argparse
import json
import math
import time

import torch

import anefx
import mimo

SCHED = {  # tuned schedules (LEDGER milestone A; milestone B shapes are added as they are tuned)
    'q16': dict(kind='ri', Nt=16, Nr=16, M=4, S=128, t0=0.7, t1=0.5, q=0.6, kappa=0.0),
    'q32': dict(kind='ri', Nt=32, Nr=32, M=4, S=128, t0=0.5, t1=0.4, q=0.4, kappa=0.0),
    'x16': dict(kind='ddi', Nt=16, Nr=16, M=16, S=256, t0=0.3, t1=0.3, q=0.4, kappa=0.0),
    'x32': dict(kind='ddi', Nt=32, Nr=32, M=16, S=256, t0=0.3, t1=0.2, q=0.4, kappa=0.3),
}


def detect(b, sc, R, kern, seed, inst0=0, z=None, Ai=None, stats=None):
    if z is None:
        z, Ai, _ = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    D = b['H'].shape[-1]
    if sc['kind'] == 'ri':
        I = mimo.ising(b, z)
        P = 1
    else:
        I = mimo.ising_delta_at(b, lm, 1)
        P = 2
    F = anefx.to_fixed(I, sc['S'], sc['t0'], sc['t1'], sc['q'], sc.get('kappa', 0.0))
    # RI: spins map one-to-one to levels, so the lowest-energy anneal is the lowest-distance one (mode 'best').
    # dDI: candidates are clipped to the constellation, which the Ising energy does not see, so every anneal's best
    # state goes to the distance-based selection, as in the float reference (mode 'chains').
    s8, e = kern.anechoic(F, R, seed, P=P, inst0=inst0, mode='best' if sc['kind'] == 'ri' else 'chains', stats=stats)
    s = s8.float()[:, None, :] if sc['kind'] == 'ri' else s8.float()
    L = mimo.spins_to_levels(s, b['M'], D) if sc['kind'] == 'ri' else mimo.spins_to_levels_delta(s, I, b['M'])
    lh, _, _ = mimo.select(b, L, lm)
    return lh


def detect_float(b, sc, R, gen, z=None, Ai=None):
    if z is None:
        z, Ai, _ = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    D = b['H'].shape[-1]
    if sc['kind'] == 'ri':
        I = mimo.ising(b, z)
        S_ = mimo.anechoic(I, R, sc['S'], sc['t0'], sc['t1'], sc['q'], kappa=sc.get('kappa', 0.0), gen=gen)
        L = mimo.spins_to_levels(S_, b['M'], D)
    else:
        I = mimo.ising_delta_at(b, lm, 1)
        S_ = mimo.anechoic(I, R, sc['S'], sc['t0'], sc['t1'], sc['q'], kappa=sc.get('kappa', 0.0), gen=gen, phases=2)
        L = mimo.spins_to_levels_delta(S_, I, b['M'])
    lh, _, _ = mimo.select(b, L, lm)
    return lh


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--cubin', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cfg', required=True)
    ap.add_argument('--sched', default=None, help='JSON schedule overriding SCHED[cfg]')
    ap.add_argument('--rho', type=float, default=0.0)
    ap.add_argument('--snrs', required=True)
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--batch', type=int, default=4000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--anneals', default='16,64')
    ap.add_argument('--float', action='store_true', help='also run the float reference on the same draws')
    a = ap.parse_args()
    torch.backends.cuda.matmul.allow_tf32 = False
    sc = dict(SCHED.get(a.cfg, {}))
    if a.sched:
        sc.update(json.loads(a.sched))
    kern = anefx.Kernel(a.cubin)
    fo = open(a.out + '.jsonl', 'a')
    for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
        for R in (int(x) for x in a.anneals.split(',')):
            acc = {'fx': [0, 0, 0.0], 'float': [0, 0, 0.0]}
            for bi in range(math.ceil(a.n / a.batch)):
                B = min(a.batch, a.n - bi * a.batch)
                g = torch.Generator(device='cuda'); g.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi)
                b = mimo.make_batch(B, sc['Nt'], sc['Nr'], sc['M'], snr, g, rho=a.rho)
                z, Ai, _ = mimo.mmse(b)
                torch.cuda.synchronize(); t0 = time.time()
                lh = detect(b, sc, R, kern, seed=a.seed * 1_000_003 + si * 10_007 + bi + 7919, z=z, Ai=Ai)
                torch.cuda.synchronize(); acc['fx'][2] += time.time() - t0
                e, nb = mimo.bit_errors(b, lh); acc['fx'][0] += e; acc['fx'][1] += nb
                if a.float:
                    gs = torch.Generator(device='cuda'); gs.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi + 7919)
                    torch.cuda.synchronize(); t0 = time.time()
                    lh = detect_float(b, sc, R, gs, z=z, Ai=Ai)
                    torch.cuda.synchronize(); acc['float'][2] += time.time() - t0
                    e, nb = mimo.bit_errors(b, lh); acc['float'][0] += e; acc['float'][1] += nb
            for k in (('fx', 'float') if a.float else ('fx',)):
                r = dict(cfg=a.cfg, nt=sc['Nt'], nr=sc['Nr'], M=sc['M'], rho=a.rho, snr=snr, impl=k, anneals=R, n=a.n,
                         seed=a.seed, err=acc[k][0], bits=acc[k][1], ber=acc[k][0] / acc[k][1], seconds=acc[k][2],
                         sched=sc)
                fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)
