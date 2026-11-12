#!/usr/bin/env python3
"""A5.4 flip calibration (tuning seed 1000 only; PROTOCOL_A54.md section 3): as calib_flips.py, per Sk. Resumes from OUT.
Usage: calib_flips_a54.py OUT.json"""
import json, os, sys, torch, apx
OUT = sys.argv[1]
torch.cuda.set_per_process_memory_fraction(0.30, 0)
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
for Sk in (128, 32, 64, 256, 512, 1024, 2048, 4096, 8192):
    for shape, snr, Ns, B in (('x16', 20.0, 32, 2000), ('x32', 22.0, 8, 1000)):
        key = '%s/%d' % (shape, Sk)
        if key in res or (shape == 'x16' and Sk > 4096):
            continue
        s = apx.SHAPES[shape]; c = s['mdi']; cnt = {}
        b = apx.draw(1000, snr, 50, B, s['nt'], s['M'])
        gs = torch.Generator(device='cuda'); gs.manual_seed(1000)
        solver = lambda I, na, K: apx.anechoic_colour(I, na, 0.3, 0.4, 2 * K, 1, Sk=Sk, gen=gs, count=cnt)
        apx.mdi_diag(b, solver, Ns, c['Rmax'], c['S'], guesses=c['guesses'])
        res[key] = {str(K): dict(v, phi=v['flips'] / v['steps'], F=v['flips'] / v['anneals'], L=v['steps'] / v['anneals'])
                    for K, v in cnt.items() if K != '_K'}
        with open(OUT + '.tmp', 'w') as f:
            json.dump(res, f, indent=1)
        os.rename(OUT + '.tmp', OUT)
        print(key, {K: round(v['phi'], 5) for K, v in res[key].items()}, flush=True)
print('CALIBRATION DONE', flush=True)
