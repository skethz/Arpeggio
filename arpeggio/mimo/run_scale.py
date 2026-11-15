#!/usr/bin/env python3
"""Scaling sweep: uncoded BER of MMSE, MMSE-SIC, K-best (a ladder of K), the sphere decoder
(optional, node counts) and Chord on the custom kernel (a ladder of anneal counts R; RI-MIMO for QPSK, dDI K = 1
for 16-QAM), optionally MDI-AHC / MDI-Chord, on the same channel draws. One JSON line per (SNR, detector).
Seeds as run_ber.py: channel (seed, SNR index, batch index); solver seed + 7919."""
import argparse
import json
import math
import time

import numpy as np
import torch

import chordfx
import fxdetect
import mimo
import tree

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--nr', type=int, required=True)
ap.add_argument('--M', type=int, required=True)
ap.add_argument('--rho', type=float, default=0.0)
ap.add_argument('--snrs', required=True)
ap.add_argument('--n', type=int, required=True)
ap.add_argument('--batch', type=int, default=4000)
ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--K', default='1,2,4,8,16,32,64,128,256')
ap.add_argument('--R', default='1,2,4,8,16,32,64,128,256')
ap.add_argument('--sd', action='store_true')
ap.add_argument('--sd-cap', type=int, default=2_000_000)
ap.add_argument('--sched', required=True, help='JSON Chord schedule: S, t0, t1, q, kappa')
ap.add_argument('--mdi', default='', help='comma list: mdiahcN, mdichordN (N anneals per stage)')
ap.add_argument('--mdicfg', default='{"Rmax":3,"S":8,"guesses":["mmse","sic"]}')
ap.add_argument('--mdichord', default='{"Sk":64,"t0":0.3,"t1":0.3,"q":0.4,"kappa":0}')
ap.add_argument('--cubin', required=True)
ap.add_argument('--kind', default='auto', help="Chord formulation: auto (RI for QPSK, dDI for 16-QAM), ri or ddi")
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
kern = chordfx.Kernel(a.cubin)
sc = json.loads(a.sched)
sc.update(kind=('ri' if a.M == 4 else 'ddi') if a.kind == 'auto' else a.kind, Nt=a.nt, Nr=a.nr, M=a.M)
Ks = [int(x) for x in a.K.split(',') if x]
Rs = [int(x) for x in a.R.split(',') if x]
mdis = [x for x in a.mdi.split(',') if x]
mdicfg = json.loads(a.mdicfg)
mdichord = json.loads(a.mdichord)
levels = np.array(mimo.PAM[a.M]['levels'], np.float64)
names = ['mmse', 'sic'] + ['kbest%d' % K for K in Ks] + (['sd'] if a.sd else []) + ['chord%d' % R for R in Rs] + mdis
fo = open(a.out + '.jsonl', 'a')
for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
    acc = {m: dict(err=0, bits=0, verr=0, t=0.0, nodes=0, unfinished=0, anneals=0.0) for m in names}
    for bi in range(math.ceil(a.n / a.batch)):
        B = min(a.batch, a.n - bi * a.batch)
        g = torch.Generator(device='cuda'); g.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi)
        b = mimo.make_batch(B, a.nt, a.nr, a.M, snr, g, rho=a.rho)
        z, Ai, _ = mimo.mmse(b)
        lm = mimo.mmse_hard(b, z, Ai)
        Hn = yn = None
        for m in names:
            torch.cuda.synchronize(); t0 = time.time()
            if m == 'mmse':
                lh = lm
            elif m == 'sic':
                lh = mimo.mmse_sic(b, 'real')
            elif m.startswith('kbest') or m == 'sd':
                if Hn is None:
                    Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
                t0 = time.time()
                if m == 'sd':
                    xh, nodes, done = tree.sphere_decoder(Hn, yn, levels, a.sd_cap)
                    acc[m]['nodes'] += int(nodes.sum()); acc[m]['unfinished'] += int((~done).sum())
                else:
                    xh, _ = tree.kbest2(Hn, yn, levels, int(m[5:]))
                acc[m]['t'] += time.time() - t0
                lh = torch.tensor(xh, device='cuda', dtype=torch.float32)
                t0 = None
            elif m.startswith('chord'):
                lh = fxdetect.detect(b, sc, int(m[5:]), kern, seed=a.seed * 1_000_003 + si * 10_007 + bi + 7919, z=z, Ai=Ai)
            elif m.startswith('mdi'):
                gs = torch.Generator(device='cuda'); gs.manual_seed(a.seed * 1_000_003 + si * 10_007 + bi + 7919)
                Ns = int(m[6:] if m.startswith('mdiahc') else m[8:])
                if m.startswith('mdiahc'):
                    solver = lambda I_, na, K: mimo.ahc(I_, na, gen=gs)
                else:
                    solver = lambda I_, na, K: mimo.chord(I_, na, mdichord['Sk'] * 2 * K, mdichord['t0'], mdichord['t1'],
                                                             mdichord['q'], kappa=mdichord.get('kappa', 0.0), gen=gs, phases=2 * K)
                st = {}
                g_ = tuple(mdicfg['guesses']) if a.M == 16 else ('mmse',)
                Rmax, S_ = (mdicfg['Rmax'], mdicfg['S']) if a.M == 16 else (1, 1)
                lh = mimo.mdi(b, solver, Ns, Rmax, S_, guesses=g_, z_mmse=z, stats=st)
                acc[m]['anneals'] += st['anneals']
            if t0 is not None:
                torch.cuda.synchronize(); acc[m]['t'] += time.time() - t0
            e, nb = mimo.bit_errors(b, lh)
            acc[m]['err'] += e; acc[m]['bits'] += nb
            acc[m]['verr'] += int((lh != b['l']).any(-1).sum())
    for m in names:
        r = dict(nt=a.nt, nr=a.nr, M=a.M, rho=a.rho, snr=snr, method=m, n=a.n, seed=a.seed, err=acc[m]['err'],
                 bits=acc[m]['bits'], ber=acc[m]['err'] / acc[m]['bits'], vector_err=acc[m]['verr'], seconds=acc[m]['t'])
        if m == 'sd':
            r.update(mean_nodes=acc[m]['nodes'] / a.n, sd_unfinished=acc[m]['unfinished'], sd_cap=a.sd_cap)
        if m.startswith('chord'):
            r['sched'] = sc
        if m.startswith('mdi'):
            r.update(mean_anneals=acc[m]['anneals'] / a.n, mdicfg=mdicfg)
            if m.startswith('mdichord'):
                r['mdichord'] = mdichord
        fo.write(json.dumps(r) + '\n'); fo.flush()
        print(json.dumps(r), flush=True)
