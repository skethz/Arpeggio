#!/usr/bin/env python3
"""Coded BLER with soft-output detectors (DESIGN.md). Each user sends one 5G NR LDPC codeword (Sionna 2.2, k = 1024,
n = 2048, rate 1/2, 20 flooding BP iterations, boxplus-phi) per frame; the codeword's n / log2(M) symbols are sent
over that many channel uses with independent channels (fast fading); all Nt users transmit at once.
Detectors and their LLRs (positive = bit 1, as Sionna):
  mmse      unbiased Gaussian max-log LLRs (mimo.mmse_soft_llr)
  kbestK    max-log over the K-best list plus the single-bit-flip neighbours of its best leaf (mimo.list_llr);
            every list detector's LLRs are clipped to +-clip (--clip, chosen on the tuning set, the same for all lists)
  aneNA     max-log over the NA anneals' best states, the MMSE estimate and the bit-flip neighbours of the best (list_llr)
  saneNA    Anechoic's SCA rule as a posterior sampler (mimo.anechoic_soft): NA chains at T = tmult * N0 / (2 scale),
            max-log over every visited state of every chain, plus the list above (mimo.trajectory_llr)
  cimNA / ahcNA  the same list rule with Princeton's CIM / AHC-CIM solvers
  hard:X    hard decisions of X mapped to LLR +-4 (for reference: what hard output gives the decoder)
One JSON line per (method, SNR) to OUT.jsonl. Usage:
  soft.py --nt 16 --nr 16 --M 16 --snrs 14,16 --frames 200 --fbatch 20 --methods mmse,kbest32,ane64 --ane JSON --out P"""
import argparse
import json
import math
import time

import numpy as np
import torch
from sionna.phy.fec.ldpc import LDPC5GDecoder, LDPC5GEncoder

import mimo
import tree

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--nr', type=int, required=True)
ap.add_argument('--M', type=int, required=True)
ap.add_argument('--rho', type=float, default=0.0)
ap.add_argument('--snrs', required=True)
ap.add_argument('--frames', type=int, required=True)
ap.add_argument('--fbatch', type=int, default=20)
ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--methods', required=True)
ap.add_argument('--ane', default='{"S":128,"t0":0.5,"t1":0.1,"q":0.25,"kappa":0}')
ap.add_argument('--sane', default='{"S":128,"tmult":1.0,"q":0.25}')
ap.add_argument('--cim-as', type=float, default=1.0)
ap.add_argument('--cim-pump', default='time')
ap.add_argument('--clip', type=float, default=8.0)
ap.add_argument('--k', type=int, default=1024)
ap.add_argument('--n', type=int, default=2048)
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
dev = 'cuda:0'
enc = LDPC5GEncoder(a.k, a.n, device=dev)
dec = LDPC5GDecoder(enc, num_iter=20, hard_out=True, device=dev)
ane = json.loads(a.ane)
sane = json.loads(a.sane)
M, Nt = a.M, a.nt
D = 2 * Nt
nb = mimo.PAM[M]['bits']                                                   # bits per real dimension
bps = 2 * nb
nsym = a.n // bps
lv = torch.tensor(mimo.PAM[M]['levels'], device=dev, dtype=torch.float32)
gray = mimo.level_bits(M).to(dev)                                          # (L, nb)
levels_np = np.array(mimo.PAM[M]['levels'], np.float64)


def bits_to_levels(bits):
    """(..., nb) Gray bits -> integer levels."""
    idx = (bits[..., None, :] == gray).all(-1).float().argmax(-1)
    return lv[idx]


def detect_llr(b, method, gs):
    z, Ai, el2 = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    hard = method.startswith('hard:')
    m = method[5:] if hard else method
    if m == 'mmse':
        if hard:
            l_hat = lm
        else:
            return mimo.mmse_soft_llr(b, z, Ai, el2)
    elif m.startswith('kbest'):
        K = int(m[5:])
        lst, _ = tree.kbest(b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy(), levels_np, K)
        cand = torch.tensor(lst, device=dev, dtype=torch.float32)
        l_hat, allc, d = mimo.select(b, cand, lm)
    else:
        I = mimo.ising(b, z)
        na = int(m[3:]) if not m.startswith('sane') else 0
        if m.startswith('sane'):                                           # Anechoic as a posterior sampler
            na = int(m[4:])
            bl, bd, m0, m1 = mimo.anechoic_soft(I, b, na, sane['S'], sane.get('tmult', 1.0), sane['q'], t_hot=sane.get('t_hot'),
                                                hot_frac=sane.get('hot_frac', 0.0), gen=gs, t_abs=sane.get('t_abs'),
                                                reg=sane.get('reg', False), warm=sane.get('warm', False))
            l_hat, llr = mimo.trajectory_llr(b, bl, bd, m0, m1, lm, clip=a.clip)
            if hard:
                return (mimo.levels_to_bits(l_hat, M).float() * 2 - 1) * 4.0
            return llr
        if m.startswith('ane'):
            S_ = mimo.anechoic(I, na, ane['S'], ane['t0'], ane['t1'], ane['q'], kappa=ane.get('kappa', 0.0),
                               lam=ane.get('lam', 0.0), gen=gs)
        elif m.startswith('cim'):
            S_ = mimo.cim(I, na, As=a.cim_as, pump=a.cim_pump, gen=gs)
        elif m.startswith('ahc'):
            S_ = mimo.ahc(I, na, gen=gs)
        else:
            raise SystemExit('unknown method ' + method)
        l_hat, allc, d = mimo.select(b, mimo.spins_to_levels(S_, M, D), lm)
    if hard:
        return (mimo.levels_to_bits(l_hat, M).float() * 2 - 1) * 4.0
    return mimo.list_llr(b, allc, d, l_hat, clip=a.clip)


fo = open(a.out + '.jsonl', 'a')
for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
    for method in a.methods.split(','):
        nerr_cw, ncw, nbit_err, nbits, t_det = 0, 0, 0, 0, 0.0
        for fb in range(math.ceil(a.frames / a.fbatch)):
            F = min(a.fbatch, a.frames - fb * a.fbatch)
            g = torch.Generator(device=dev); g.manual_seed(a.seed * 1_000_003 + si * 10_007 + fb)
            gs = torch.Generator(device=dev); gs.manual_seed(a.seed * 1_000_003 + si * 10_007 + fb + 7919)
            u = torch.randint(0, 2, (F, Nt, a.k), generator=g, device=dev).float()
            c = enc(u)                                                     # (F, Nt, n)
            cb = c.reshape(F, Nt, nsym, 2, nb)                             # per symbol: Re bits, Im bits
            lre = bits_to_levels(cb[..., 0, :])                            # (F, Nt, nsym)
            lim = bits_to_levels(cb[..., 1, :])
            l = torch.cat([lre, lim], 1).permute(0, 2, 1).reshape(F * nsym, D)   # dims: Re users, then Im users
            b = mimo.make_batch(F * nsym, Nt, a.nr, M, snr, g, rho=a.rho, levels=l)
            torch.cuda.synchronize(); t0 = time.time()
            llr = detect_llr(b, method, gs)                                # (B, D * nb), dim-major, MSB first
            torch.cuda.synchronize(); t_det += time.time() - t0
            llr = llr.reshape(F, nsym, 2, Nt, nb).permute(0, 3, 1, 2, 4).reshape(F, Nt, a.n)
            uh = dec(llr.clamp(-20, 20))
            cw_err = (uh != u).any(-1)
            nerr_cw += int(cw_err.sum()); ncw += cw_err.numel()
            nbit_err += int(((llr > 0).float() != c).sum()); nbits += c.numel()
        r = dict(nt=Nt, nr=a.nr, M=M, rho=a.rho, snr=snr, method=method, frames=a.frames, codewords=ncw, cw_errors=nerr_cw,
                 bler=nerr_cw / ncw, raw_ber=nbit_err / nbits, k=a.k, n=a.n, seed=a.seed, det_seconds=t_det, clip=a.clip)
        if 'sane' in method:
            r['sane'] = sane
        elif 'ane' in method:
            r['ane'] = ane
        if 'cim' in method:
            r['cim_as'] = a.cim_as; r['cim_pump'] = a.cim_pump
        fo.write(json.dumps(r) + '\n'); fo.flush()
        print(json.dumps(r), flush=True)
