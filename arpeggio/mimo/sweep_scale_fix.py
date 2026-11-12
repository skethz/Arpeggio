#!/usr/bin/env python3
"""Held-out scaling sweeps (seed 1) for every milestone-B configuration: grids placed from the tuning-set pre-scan,
Anechoic schedules = the best of tuning rounds 1 and 2 on the i.i.d. channel of the same shape and modulation
(reused for rho = 0.5), K-best and anneal ladders 1..256, the sphere decoder, and for 32x64 Princeton's published
massive-MIMO MDI settings (QPSK: DI-MIMO, 64 anneals; 16-QAM: Ns 8, R_max 3, S 8) with AHC and with Anechoic.
About 4e5 bits per SNR point. Usage: sweep_scale.py CUBIN OUTDIR [SHAPES]"""
import json
import os
import subprocess
import sys

cubin, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
best = {}
for f in ('../results/tune_scale/tune.jsonl', '../results/tune_scale/tune_r2.jsonl'):
    for l in open(f):
        r = json.loads(l)
        if 'best' in r:
            continue
        k = (r['nt'], r['nr'], r['M'])
        if k not in best or r['ber'] < best[k]['ber']:
            best[k] = r
GRID = {  # (nt, nr, M, rho) -> SNR list (dB)
    (64, 64, 4, 0.0): range(8, 17), (64, 64, 4, 0.5): range(10, 19),
    (16, 64, 4, 0.0): range(1, 7), (16, 64, 4, 0.5): range(1, 8),
    (16, 128, 4, 0.0): range(-2, 4), (16, 128, 4, 0.5): range(-2, 4),
    (32, 64, 4, 0.0): range(4, 12), (32, 64, 4, 0.5): range(4, 13),
    (32, 128, 4, 0.0): range(1, 7), (32, 128, 4, 0.5): range(1, 8),
    (64, 64, 16, 0.0): range(18, 29), (64, 64, 16, 0.5): range(20, 33),
    (16, 64, 16, 0.0): range(8, 14), (16, 64, 16, 0.5): range(8, 15),
    (16, 128, 16, 0.0): range(5, 11), (16, 128, 16, 0.5): range(5, 11),
    (32, 64, 16, 0.0): range(11, 19), (32, 64, 16, 0.5): range(11, 20),
    (32, 128, 16, 0.0): range(8, 14), (32, 128, 16, 0.5): range(8, 15),
}
order = sorted(GRID, key=lambda k: (k[0] == 64, k[2], k[3], k[0], k[1]))   # 64x64 last (the slowest)
if len(sys.argv) > 3:                       # a subset, e.g. "16x128" (rerun of configurations that failed)
    order = [k for k in order if '%dx%d' % (k[0], k[1]) in sys.argv[3].split(',')]
for nt, nr, M, rho in order:
    sc = best[(nt, nr, M)]['sched']
    sched = {k: sc[k] for k in ('S', 't0', 't1', 'q', 'kappa')}
    bits = 2 * nt * (1 if M == 4 else 2)
    n = int(4e5 / bits)
    batch = min(n, 4000)
    n = batch * ((n + batch - 1) // batch)
    tag = '%s%dx%d%s' % ('q' if M == 4 else 'x', nt, nr, '_rho05' if rho else '')
    cmd = ['python', 'run_scale.py', '--nt', str(nt), '--nr', str(nr), '--M', str(M), '--rho', str(rho),
           '--snrs=' + ','.join(str(s) for s in GRID[(nt, nr, M, rho)]), '--n', str(n), '--batch', str(batch),
           '--seed', '1', '--sd', '--sched', json.dumps(sched), '--cubin', cubin, '--out', os.path.join(out, tag)]
    if (nt, nr) == (32, 64):
        cmd += ['--mdi', 'mdiahc64,mdiane64' if M == 4 else 'mdiahc8,mdiane8']
    print(' '.join(cmd), flush=True)
    rc = subprocess.call(cmd, stdout=open(os.path.join(out, tag + '.log'), 'w'), stderr=subprocess.STDOUT)
    print(tag, 'exit', rc, flush=True)
print('SWEEP_SCALE_DONE')
