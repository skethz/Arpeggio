#!/usr/bin/env python3
"""LLR calibration on the tuning set (seed 1000): for each detector, the scale alpha minimising the bit cross-entropy
of alpha * LLR at the given SNRs (uncoded channel uses, uniform symbols), with the BCE at alpha = 1 for reference and
the reliability table (|LLR| bins: share, empirical and predicted P(correct)) before and after. JSON lines to OUT.jsonl.
Usage: calib.py --nt 16 --nr 16 --M 16 --snrs 14,16 --n 4000 --methods kbest32,ane64,sane64,cim64 --out P [cfg flags]"""
import argparse
import json

import torch

import mimo
import softlib

ap = argparse.ArgumentParser()
ap.add_argument('--nt', type=int, required=True)
ap.add_argument('--nr', type=int, required=True)
ap.add_argument('--M', type=int, required=True)
ap.add_argument('--rho', type=float, default=0.0)
ap.add_argument('--snrs', required=True)
ap.add_argument('--n', type=int, default=4000)
ap.add_argument('--batch', type=int, default=2000)
ap.add_argument('--methods', required=True)
ap.add_argument('--ane', default='{"S":128,"t0":0.5,"t1":0.5,"q":0.6,"kappa":0}')
ap.add_argument('--sane', default='{"S":128,"t_abs":0.4,"q":0.4,"reg":true}')
ap.add_argument('--aned', default='{"S":256,"t0":0.2,"t1":0.1,"q":0.2,"phases":2}')
ap.add_argument('--cim-as', type=float, default=1.5)
ap.add_argument('--cim-pump', default='time')
ap.add_argument('--out', required=True)
a = ap.parse_args()
torch.backends.cuda.matmul.allow_tf32 = False
cfg = dict(ane=json.loads(a.ane), sane=json.loads(a.sane), aned=json.loads(a.aned), cim_as=a.cim_as, cim_pump=a.cim_pump)
fo = open(a.out + '.jsonl', 'a')


def table(L, bits):
    corr = ((L > 0) == bits.bool()).float().flatten()
    x = L.abs().flatten()
    rows = []
    for lo, hi in zip([0, 1, 2, 4, 8, 16], [1, 2, 4, 8, 16, 1e9]):
        m = (x >= lo) & (x < hi)
        if m.any():
            rows.append(dict(bin=[lo, hi], share=float(m.float().mean()), emp=float(corr[m].mean()), pred=float(torch.sigmoid(x[m]).mean())))
    return rows


for method in a.methods.split(','):
    Ls, Bs = [], []
    for si, snr in enumerate(float(x) for x in a.snrs.split(',')):
        for bi in range(0, a.n, a.batch):
            B = min(a.batch, a.n - bi)
            g = torch.Generator(device='cuda'); g.manual_seed(1000 * 1_000_003 + si * 10_007 + bi)
            gs = torch.Generator(device='cuda'); gs.manual_seed(1000 * 1_000_003 + si * 10_007 + bi + 7919)
            b = mimo.make_batch(B, a.nt, a.nr, a.M, snr, g, rho=a.rho)
            llr, _ = softlib.detect_llr(b, method, gs, cfg)
            Ls.append(llr); Bs.append(mimo.levels_to_bits(b['l'], a.M))
    L, bits = torch.cat(Ls), torch.cat(Bs)
    al, bce_a, bce_1 = softlib.fit_alpha(L, bits)
    r = dict(nt=a.nt, nr=a.nr, M=a.M, rho=a.rho, snrs=a.snrs, n=a.n, method=method, alpha=al, bce_alpha=bce_a, bce_1=bce_1,
             sign_err=float(((L > 0) != bits.bool()).float().mean()), mean_abs=float(L.abs().mean()),
             table_raw=table(L, bits), table_cal=table(al * L, bits), cfg=cfg)
    fo.write(json.dumps(r) + '\n'); fo.flush()
    print(json.dumps(dict(method=method, alpha=round(al, 4), bce_alpha=round(bce_a, 4), bce_1=round(bce_1, 4), sign_err=round(r['sign_err'], 4))), flush=True)
