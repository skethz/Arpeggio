#!/usr/bin/env python3
"""A5.21 dry test (no GPU, synthetic batches): planner gating and order, then the analysis on fake data. Usage: sim_a521.py SRC TMP"""
import json, os, subprocess, sys, shutil
import numpy as np
SRC, T = sys.argv[1], sys.argv[2]
PY = sys.executable
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
def plan():
    out = subprocess.run([PY, os.path.join(SRC, 'a521_plan.py'), T], capture_output=True, text=True, check=True).stdout.split()
    return [int(x) for x in out], json.load(open(os.path.join(T, 'plan.json')))['jobs'], json.load(open(os.path.join(T, 'select.json')))
(n, g, hd), jobs, sel = plan()
assert n == 4 and g == 0 and hd == 0 and all(j['set'].startswith('g') for j in jobs) and all(j['seed'] == 102 and j['saved'] for j in jobs), jobs
def mk(j, bi, err):
    d = os.path.join(T, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr']); os.makedirs(d, exist_ok=True)
    B = j['batch']; be = np.zeros(B, np.uint8); be[:err] = 3
    cnt = {'cnt': {'1': dict(flips=10.0 * B, tests=100.0 * B, decisions=(256 if 'fam_4' in j['method'] else 256) * B, anneals=float(B), N=64)}}
    np.savez(os.path.join(d, 'b%05d.npz' % bi), biterr=be, info=np.array(json.dumps(dict(method=j['method'], bi=bi, cnt=cnt))))
    return d
for j in jobs:
    d = mk(j, 0, 1); json.dump({}, open(os.path.join(d, 'done.json'), 'w'))
(n, g, hd), jobs, sel = plan()
assert g == 1 and hd == 0 and n == 2 * 15 + 2 * 30, (n, g)
assert jobs[0]['set'] == 'h_P2_c000' and jobs[0]['method'] == 'mdichord8' and jobs[1]['method'].startswith('abl_fam_2') and \
    jobs[2]['set'] == 'h_P1_c000' and jobs[2]['method'] == 'mdichord32', jobs[:3]
assert {j['seed'] for j in jobs} == {2028} and sum(j['n_batches'] for j in jobs if j['shape'] == 'x16') == 300 and \
    sum(j['n_batches'] for j in jobs if j['shape'] == 'x32') == 600
fr = [(int(j['set'][-3:]) + 0.5) / (15 if j['shape'] == 'x16' else 30) for j in jobs]
assert fr == sorted(fr), 'not interleaved by fraction'
for j in jobs:                                                     # full run: SA 3x the errors of C0
    for b in range(j['first_batch'], j['first_batch'] + j['n_batches']):
        mk(j, b, 6 if 'fam' in j['method'] else 2)
    json.dump({}, open(os.path.join(T, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json'), 'w'))
(n, g, hd), jobs, sel = plan()
assert n == 0 and hd == 1, (n, hd)
r = subprocess.run([PY, os.path.join(SRC, 'analyze_a521.py'), T, os.path.join(T, 'analysis.json')], capture_output=True, text=True,
                   cwd='<SCRATCH>/arpeggio_ber_20261024/src', env=dict(os.environ, PYTHONPATH='<SCRATCH>/arpeggio_ber_20261024/src'))
print(r.stdout, r.stderr[-2000:])
a = json.load(open(os.path.join(T, 'analysis.json')))
for pt, N in (('P1', 150), ('P2', 300)):
    o = a['points'][pt]
    assert abs(o['ratio'] - 3.0) < 1e-9 and o['term'] == 'Chord leads' and o['batches'] == N and not o['partial'], o
print('SIM PASS')
