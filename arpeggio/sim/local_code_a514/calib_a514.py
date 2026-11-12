#!/usr/bin/env python3
"""A5.14/A5.15 cycle calibration (tuning seed 1000 only), as calib_flips_a55.py: draw batch index 50 of seed 1000 at the point,
solver seed 1000, run apx.detect through runner_a55's counting hook, and store per-K counters. P1 1,000 uses, P2 500, P4 500.
x per K = (tests + flips) / anneals over the reference cost (first-accept), or (steps + flips) / anneals (Chord arms);
reference cost: P1/P2 L_K (1 + phi_K) with L_K = 256 K and phi from tuned_a52.json (A5.5); P4 A5.8's ref_cost (select.json).
x = mean over K. Resumes from OUT. Usage: calib_a514.py OUT POINT METHOD [METHOD ...]"""
import json
import os
import sys

import torch

import apx
import apx514
import mdi_solvers
import runner_a55  # noqa: F401  (counting hook on apx.detect)

c = mdi_solvers.MDI[('64x64', 16)]
apx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(c['Rmax']), S=int(c['S']), guesses=tuple(c['guesses'])), Ns_pub=None))
apx514.install()
R = '<SCRATCH>/ap_ber_20261024/results'
PTS = dict(P1=('x16', 20.0, 1000), P2=('x32', 22.0, 500), P4=('x64', 22.0, 500))
OUT, PT, METHODS = sys.argv[1], sys.argv[2], sys.argv[3:]
shape, snr, B = PTS[PT]
PHI = json.load(open(R + '/tuned_a52.json'))['flip_phi']
if PT == 'P4':
    REF = {str(k): float(v) for k, v in json.load(open(R + '/a58/select.json'))['ref_cost'].items()}
else:
    REF = {str(K): 256 * K * (1 + PHI[shape][str(K)]) for K in (1, 2, 3)}
ctx = apx.Ctx(json.load(open(R + '/tuned_a52.json')))
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
s = apx.SHAPES[shape]
for m in METHODS:
    key = '%s/%s' % (PT, m)
    if key in res:
        continue
    b = apx.draw(1000, snr, 50, B, s['nt'], s['M'])
    gs = torch.Generator(device='cuda'); gs.manual_seed(1000)
    z, _, _ = apx.mimo.mmse(b)
    _, _, info = apx.detect(m, b, shape, gs, ctx, z=z)
    per = {}
    for K, v in info['count'].items():
        work = v['tests'] if 'tests' in v else v['steps']
        per[K] = dict(v, F=v['flips'] / v['anneals'], cyc=(work + v['flips']) / v['anneals'], x=(work + v['flips']) / v['anneals'] / REF[K])
    res[key] = dict(point=PT, method=m, per_K=per, x=sum(p['x'] for p in per.values()) / len(per), uses=B, ref=REF)
    with open(OUT + '.tmp', 'w') as f:
        json.dump(res, f, indent=1)
    os.replace(OUT + '.tmp', OUT)
    print(key, 'x = %.4f' % res[key]['x'], {K: round(p['x'], 4) for K, p in per.items()}, flush=True)
print('CALIBRATION DONE', flush=True)
