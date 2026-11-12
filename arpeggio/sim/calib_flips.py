#!/usr/bin/env python3
"""A5d calibration (tuning seed 1000 only): Antiphase's mean flips per half-step per anneal inside MDI, per point and
sub-problem size K (colour sweep m = 1 = Antiphase, frozen T 0.3, q 0.4), at P1 (x16 20 dB Ns 32), P2 (x32 22 dB Ns 8),
P3 (q32 14 dB Ns 8). The A5d budgets use F = phi * L flips per anneal (L = 128 * 2K half-steps). Refuses to overwrite.
Usage: calib_flips.py OUT.json"""
import json, os, sys, torch, apx, mimo
OUT = sys.argv[1]
if os.path.exists(OUT):
    sys.exit('refusing: exists')
res, raw = {}, {}
for shape, snr, Ns, B, nb in (('x16', 20.0, 32, 2000, 1), ('x32', 22.0, 8, 1000, 1), ('q32', 14.0, 8, 4000, 1)):
    s = apx.SHAPES[shape]
    cnt = {}
    for bi in range(nb):
        b = apx.draw(1000, snr, 50 + bi, B, s['nt'], s['M'])
        gs = torch.Generator(device='cuda'); gs.manual_seed(1000 + bi)
        solver = lambda I, na, K: apx.anechoic_colour(I, na, 0.3, 0.4, 2 * K, 1, gen=gs, count=cnt)
        c = s['mdi']
        apx.mdi_diag(b, solver, Ns, c['Rmax'], c['S'], guesses=c['guesses'])
    res[shape] = {str(K): v['flips'] / v['steps'] for K, v in cnt.items() if K != '_K'}
    raw[shape] = {str(K): v for K, v in cnt.items() if K != '_K'}
    print(shape, json.dumps(res[shape]), flush=True)
json.dump(dict(flip_phi=res, raw=raw, note='seed 1000 draws (batch index 50+), not held-out'), open(OUT, 'w'), indent=1)
