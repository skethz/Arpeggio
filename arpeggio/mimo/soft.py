#!/usr/bin/env python3
"""Coded BLER with soft-output detectors (DESIGN.md). Each user sends one 5G NR LDPC codeword (Sionna 2.2, rate k/n,
20 flooding BP iterations, boxplus-phi) per frame; its n / log2(M) symbols go over that many channel uses with
independent channels (fast fading); all Nt users transmit at once. Detectors: softlib.detect_llr. List detectors' LLRs
are multiplied by their calibration factor alpha (--alpha JSON {method: alpha}, fitted on the tuning set by calib.py;
1 if absent) and clipped to +-20 (the decoder's llr_max). 'hard:X' feeds X's hard decisions as LLRs +-4.
One JSON line per (method, SNR). (soft_v1_dev.py: the first version, before calibration.) Usage:
  soft.py --nt 16 --nr 16 --M 16 --snrs 14,16 --frames 200 --fbatch 20 --methods mmse,kbest32,ane64 --k 1024 --n 2048
          --ane JSON --sane JSON --alpha JSON --out PREFIX"""
import argparse
import json
import math
import time

import torch
from sionna.phy.fec.ldpc import LDPC5GDecoder, LDPC5GEncoder

import mimo
import softlib

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
ap.add_argument('--ane', default='{"S":128,"t0":0.5,"t1":0.5,"q":0.6,"kappa":0}')
ap.add_argument('--sane', default='{"S":128,"t_abs":0.4,"q":0.4,"reg":true}')
ap.add_argument('--aned', default='{"S":256,"t0":0.2,"t1":0.1,"q":0.2,"phases":2}')
ap.add_argument('--cim-as', type=float, default=1.5)
ap.add_argument('--cim-pump', default='time')
ap.add_argument('--alpha', default='{}')
ap.add_argument('--k', type=int, default=1024)
ap.add_argument('--n', type=int, default=2048)
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
dev = 'cuda:0'
enc = LDPC5GEncoder(a.k, a.n, device=dev)
dec = LDPC5GDecoder(enc, num_iter=20, hard_out=True, device=dev)
cfg = dict(ane=json.loads(a.ane), sane=json.loads(a.sane), aned=json.loads(a.aned), cim_as=a.cim_as, cim_pump=a.cim_pump)
alpha = json.loads(a.alpha)
M, Nt = a.M, a.nt
D = 2 * Nt
nb = mimo.PAM[M]['bits']
bps = 2 * nb
assert a.n % bps == 0
nsym = a.n // bps
lv = torch.tensor(mimo.PAM[M]['levels'], device=dev, dtype=torch.float32)
gray = mimo.level_bits(M).to(dev)


def bits_to_levels(bits):
    idx = (bits[..., None, :] == gray).all(-1).float().argmax(-1)
    return lv[idx]


fo = open(a.out + '.jsonl', 'a')
for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
    for method in a.methods.split(','):
        hard = method.startswith('hard:')
        m = method[5:] if hard else method
        nerr_cw, ncw, nbit_err, nbits, t_det = 0, 0, 0, 0, 0.0
        for fb in range(math.ceil(a.frames / a.fbatch)):
            F = min(a.fbatch, a.frames - fb * a.fbatch)
            g = torch.Generator(device=dev); g.manual_seed(a.seed * 1_000_003 + si * 10_007 + fb)
            gs = torch.Generator(device=dev); gs.manual_seed(a.seed * 1_000_003 + si * 10_007 + fb + 7919)
            u = torch.randint(0, 2, (F, Nt, a.k), generator=g, device=dev).float()
            c = enc(u)                                                     # (F, Nt, n)
            cb = c.reshape(F, Nt, nsym, 2, nb)
            l = torch.cat([bits_to_levels(cb[..., 0, :]), bits_to_levels(cb[..., 1, :])], 1).permute(0, 2, 1).reshape(F * nsym, D)
            b = mimo.make_batch(F * nsym, Nt, a.nr, M, snr, g, rho=a.rho, levels=l)
            torch.cuda.synchronize(); t0 = time.time()
            llr, l_hat = softlib.detect_llr(b, m, gs, cfg)
            torch.cuda.synchronize(); t_det += time.time() - t0
            if hard:
                llr = (mimo.levels_to_bits(l_hat, M).float() * 2 - 1) * 4.0
            else:
                llr = (llr * alpha.get(m, 1.0)).clamp(-20, 20)
            llr = llr.reshape(F, nsym, 2, Nt, nb).permute(0, 3, 1, 2, 4).reshape(F, Nt, a.n)
            uh = dec(llr)
            cw_err = (uh != u).any(-1)
            nerr_cw += int(cw_err.sum()); ncw += cw_err.numel()
            nbit_err += int(((llr > 0).float() != c).sum()); nbits += c.numel()
        r = dict(nt=Nt, nr=a.nr, M=M, rho=a.rho, snr=snr, method=method, frames=a.frames, codewords=ncw, cw_errors=nerr_cw,
                 bler=nerr_cw / ncw, raw_ber=nbit_err / nbits, k=a.k, n=a.n, seed=a.seed, det_seconds=t_det,
                 alpha=alpha.get(m, 1.0))
        if 'sane' in m:
            r['sane'] = cfg['sane']
        elif 'ane' in m:
            r['ane'] = cfg['ane']
        if 'cim' in m:
            r['cim_as'] = a.cim_as; r['cim_pump'] = a.cim_pump
        fo.write(json.dumps(r) + '\n'); fo.flush()
        print(json.dumps(r), flush=True)
