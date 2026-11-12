#!/usr/bin/env python3
"""Milestone D: uncoded BER of PIMI and our detectors on the same held-out channel draws (mimo.make_batch, our SNR;
pimi.ebn0_to_snr converts their Eb/N0). One JSON line per (method, SNR). Methods:
  mmse          our unbiased hard MMSE (milestones A-C);   mmseb   their biased hard MMSE (PIMI's x_mmse)
  kbest32       K-best, K = 32 (CPU, numba)
  pimiS         PIMI (pimi.pimi_torch): S steps, 32 trials, the authors' settings (schedule pimi.sched_for: A for
                16-QAM, B for QPSK); pimiAS / pimiBS force schedule A or B (sensitivity)
  anedR         Antiphase, one delta stage (dDI K = 1 around MMSE; S 256 half-steps, T 0.3, q 0.4, alternating copies),
                R anneals: milestone A's frozen 16x16 schedule (= the MDI schedule at K = 1)
  mdiahcN       MDI-AHC (Singh et al. 2024, published), N anneals per stage
  mdianeN       Antiphase in the MDI wrapper (formerly MDI-Anechoic; Sk 128, T 0.3, q 0.4, 2K phases, kappa 0)
  mdiabl{v}N    ablation of Antiphase in MDI, v = i (as frozen), ii (copy alternation off: 1 phase), iii (kappa 0.3,
                Onsager kT), iv (1 phase and kappa 0.3); schedule otherwise frozen
MDI configuration per shape: --mdi JSON (Table I). Seeds: draws (seed, SNR index, batch index); solver random
numbers from a separate generator (+7919).
Usage: run_ber_d.py --nt 16 --M 16 --snrs 20 --n 8000 --batch 2000 --seed 42 --methods ... --mdi '{...}' --out PREFIX"""
import argparse
import json
import math
import time

import numpy as np
import torch

import mimo
import pimi
import tree

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--M', type=int, required=True)
ap.add_argument('--snrs', required=True, help='our SNR (dB); prefix e: for Eb/N0, e.g. e:25')
ap.add_argument('--n', type=int, required=True)
ap.add_argument('--batch', type=int, default=2000)
ap.add_argument('--seed', type=int, required=True)
ap.add_argument('--methods', required=True)
ap.add_argument('--mdi', default='{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}')
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
MA = dict(Sk=128, t0=0.3, t1=0.3, q=0.4, kappa=0.0)                       # frozen (milestone B)
ABL = {'i': (True, 0.0), 'ii': (False, 0.0), 'iii': (True, 0.3), 'iv': (False, 0.3)}   # (alternating copies, kappa)
KAPPA_A = 0.3                                                              # milestone A 32x32 16-QAM dDI schedule
methods = a.methods.split(',')
mdic = json.loads(a.mdi)
levels = np.array(mimo.PAM[a.M]['levels'], np.float64)
fo = open(a.out + '.jsonl', 'a')


def snr_of(x):
    return pimi.ebn0_to_snr(float(x[2:]), a.M) if x.startswith('e:') else float(x)


def mdi_solver(alt, kappa, gs):
    return lambda I_, na, K: mimo.anechoic(I_, na, MA['Sk'] * 2 * K, MA['t0'], MA['t1'], MA['q'], kappa=kappa, gen=gs,
                                           phases=2 * K if alt else 1)


for si, sx in enumerate(a.snrs.split(',')):
    snr = snr_of(sx)
    acc = {m: dict(err=0, bits=0, t=0.0, extra=0) for m in methods}
    nb = math.ceil(a.n / a.batch)
    for bi in range(nb):
        B = min(a.batch, a.n - bi * a.batch)
        g = torch.Generator(device='cuda'); g.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi)
        b = mimo.make_batch(B, a.nt, a.nt, a.M, snr, g)
        z, Ai, el2 = mimo.mmse(b)
        lm = mimo.mmse_hard(b, z, Ai)
        for m in methods:
            gs = torch.Generator(device='cuda'); gs.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi + 7919 + 97 * methods.index(m))
            torch.cuda.synchronize(); t0 = time.time()
            if m == 'mmse':
                lh = lm
            elif m == 'mmseb':
                lh = pimi.slice_levels(z, a.M)
            elif m.startswith('kbest'):
                Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
                lst, dd = tree.kbest(Hn, yn, levels, int(m[5:]))
                lh = torch.tensor(lst[:, 0, :], device='cuda', dtype=torch.float32)
            elif m.startswith('pimi'):
                sch = m[4] if m[4] in 'AB' else None
                lh = pimi.detect_torch(b, int(m[5:] if sch else m[4:]), pimi.TRIALS, gs, z=z, sched=sch)
            elif m.startswith('aned'):
                Id = mimo.ising_delta(b, z, K=1)
                S_ = mimo.anechoic(Id, int(m[4:]), 2 * MA['Sk'], MA['t0'], MA['t1'], MA['q'], kappa=0.0, gen=gs, phases=2)
                lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, a.M), lm)
            elif m.startswith('mdi'):
                if m.startswith('mdiahc'):
                    Ns, solver = int(m[6:]), (lambda I_, na, K: mimo.ahc(I_, na, gen=gs))
                elif m.startswith('mdiane'):
                    Ns, solver = int(m[6:]), mdi_solver(True, 0.0, gs)
                elif m.startswith('mdiabl'):
                    v = m[6:].rstrip('0123456789')
                    Ns = int(m[6 + len(v):])
                    alt, kap = ABL[v]
                    solver = mdi_solver(alt, KAPPA_A if kap else 0.0, gs)
                else:
                    raise SystemExit('unknown method ' + m)
                st = {}
                lh = mimo.mdi(b, solver, Ns, mdic['Rmax'], mdic['S'], guesses=tuple(mdic['guesses']), z_mmse=z, stats=st)
                acc[m]['extra'] += st['anneals']
            else:
                raise SystemExit('unknown method ' + m)
            torch.cuda.synchronize(); acc[m]['t'] += time.time() - t0
            e, n_ = mimo.bit_errors(b, lh)
            acc[m]['err'] += e; acc[m]['bits'] += n_
    for m in methods:
        r = dict(nt=a.nt, nr=a.nt, M=a.M, snr=snr, snr_arg=sx, ebn0=snr - 10 * math.log10(math.log2(a.M)), method=m,
                 n=a.n, seed=a.seed, err=acc[m]['err'], bits=acc[m]['bits'], ber=acc[m]['err'] / acc[m]['bits'],
                 seconds=acc[m]['t'])
        if m.startswith('mdi'):
            r['mdi'] = mdic; r['mean_anneals'] = acc[m]['extra'] / a.n
            if m.startswith('mdiabl'):
                v = m[6:].rstrip('0123456789'); r['ablation'] = dict(variant=v, alternating=ABL[v][0],
                                                                     kappa=KAPPA_A if ABL[v][1] else 0.0)
            if not m.startswith('mdiahc'):
                r['mdiane'] = MA
        if m.startswith('pimi'):
            sch = m[4] if m[4] in 'AB' else pimi.sched_name(a.nt, a.M)
            st_ = int(m[5:]) if m[4] in 'AB' else int(m[4:])
            r['pimi'] = dict(steps=st_, trials=pimi.TRIALS, schedule=sch, beta=pimi.SCHED[sch][0], gamma=pimi.SCHED[sch][1],
                             frac_bits=pimi.FRAC)
        if m.startswith('aned'):
            r['aned'] = dict(S=2 * MA['Sk'], t0=MA['t0'], t1=MA['t1'], q=MA['q'], phases=2)
        fo.write(json.dumps(r) + '\n'); fo.flush()
        print(json.dumps(r), flush=True)
