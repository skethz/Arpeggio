#!/usr/bin/env python3
"""A5.3c (PROTOCOL_A53.md): sequential SA's accepted flips per anneal inside MDI, on tuning seed 1000 (batch index 50+,
as calib_flips.py), for both picks (sa2 = 2.4 -> 0.0125; old = 2.4 -> 0.05) and S in {1, 2, ..., 128}, at P1 (x16 20 dB
Ns 32, 1,000 uses) and P2 (x32 22 dB Ns 8, 500 uses). Cycles per anneal = S * N + F_SA (A5.1 model). Writes OUT.json
incrementally (one entry per shape/pick/S; restartable: finished entries are kept). Usage: calib_flips_sa.py OUT.json"""
import json, os, sys, torch, apx
OUT = sys.argv[1]
res = json.load(open(OUT)) if os.path.exists(OUT) else dict(note='seed 1000 draws (batch index 50+), not held-out', F={})
PICKS = {'sa2': (2.4, 0.0125), 'old': (2.4, 0.05)}
for shape, snr, Ns, B in (('x16', 20.0, 32, 1000), ('x32', 22.0, 8, 500)):
    s = apx.SHAPES[shape]
    c = s['mdi']
    for pick, (T0, T1) in PICKS.items():
        for S in (1, 2, 4, 8, 16, 32, 64, 128):
            key = '%s/%s/%d' % (shape, pick, S)
            if key in res['F']:
                continue
            b = apx.draw(1000, snr, 50, B, s['nt'], s['M'])
            gs = torch.Generator(device='cuda'); gs.manual_seed(1000)
            cnt = {}
            solver = lambda I, na, K: apx.sa_seq(I, na, S, T0, T1, K, gen=gs, count=cnt)
            apx.mdi_diag(b, solver, Ns, c['Rmax'], c['S'], guesses=c['guesses'])
            res['F'][key] = {str(K): dict(N=v['N'], F_per_anneal=v['flips'] / v['anneals'], decisions_per_anneal=v['decisions'] / v['anneals'],
                                          acc_frac=v['flips'] / v['decisions'], anneals=v['anneals']) for K, v in cnt.items()}
            json.dump(res, open(OUT + '.tmp', 'w'), indent=1)
            os.replace(OUT + '.tmp', OUT)
            print(key, json.dumps(res['F'][key]), flush=True)
print('DONE', flush=True)
