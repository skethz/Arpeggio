#!/usr/bin/env python3
"""A5.5 flip calibration (tuning seed 1000 only; PROTOCOL_A55.md section 7): for every held-out pick, F, tests and N per K on batch
index 50, 1,000 uses at P1, 500 at P2, 2,000 at P3, solver seed 1000, as A5.3c. Resumes from OUT. Usage: calib_flips_a55.py OUT SELECT"""
import json, os, sys, torch, apx, runner_a55  # noqa: F401
OUT, SEL = sys.argv[1], sys.argv[2]
ctx = apx.Ctx(json.load(open('<SCRATCH>/ap_ber_20261024/results/tuned_a52.json')))
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
held = json.load(open(SEL))['held']
for pt, (shape, snr, B) in dict(P1=('x16', 20.0, 1000), P2=('x32', 22.0, 500), P3=('q32', 14.0, 2000)).items():
    s = apx.SHAPES[shape]
    for m in held[pt]:
        if m in res or m.startswith('abl_ptb_'):
            continue
        b = apx.draw(1000, snr, 50, B, s['nt'], s['M'])
        gs = torch.Generator(device='cuda'); gs.manual_seed(1000)
        z, _, _ = apx.mimo.mmse(b)
        _, _, info = apx.detect(m, b, shape, gs, ctx, z=z)
        res[m] = {K: dict(v, F=v['flips'] / v['anneals']) for K, v in info['count'].items()}
        with open(OUT + '.tmp', 'w') as f:
            json.dump(res, f, indent=1)
        os.replace(OUT + '.tmp', OUT)
        print(m, {K: round(v['F'], 1) for K, v in res[m].items()}, flush=True)
print('CALIBRATION DONE', flush=True)
