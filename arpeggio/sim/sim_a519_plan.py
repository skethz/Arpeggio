#!/usr/bin/env python3
"""Synthetic run of a519_plan.py and analyze_a519.py to the end (no GPU). Fakes every queued job (done.json plus batch files with
counters, toy BER and cycles) and checks seeds, sizes, queue order, corners, stage B, the S* rule with grid
extension, held-out coverage, and that no held-out arm that depends on a pick is queued before the pick exists.
Usage: sim_a519_plan.py SRC_DIR A58_SELECT_JSON [xc]   (xc: the fake re-tuned Chord's calibrated x; default 1.40 forces an upward extension)"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

SRC, A58 = sys.argv[1], sys.argv[2]
XC = float(sys.argv[3]) if len(sys.argv) > 3 else 1.40
T = tempfile.mkdtemp(prefix='sim_a519_')
os.makedirs(os.path.join(T, 'a58')); shutil.copy(A58, os.path.join(T, 'a58', 'select.json'))
shutil.copy(os.path.join(os.path.dirname(A58), '..', 'tuned_a52.json'), os.path.join(T, 'tuned_a52.json'))
R = os.path.join(T, 'a519'); os.makedirs(R)
REF = {str(k): float(v) for k, v in json.load(open(A58))['ref_cost'].items()}
rng = np.random.default_rng(0)
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def toy_x(m):
    a = m.split('_')
    if m.startswith('abl_far_'):
        return 0.115 + 0.007 * int(a[2])
    if m.startswith('abl_chord_'):
        T0, q = float(a[2]), float(a[4])
        return XC if m == 'abl_chord_0.6_0.1_0.4_rand_8' else 1.0 + 0.3 * T0 - 0.2 * q
    return 1.0


def toy_ber(m):
    if m.startswith('abl_chord_'):
        a = m.split('_'); T0, T1, q = float(a[2]), float(a[3]), float(a[4])
        return 3e-4 * (1 + abs(np.log(T0 / 0.6)) + abs(np.log(T1 / 0.1)) + abs(q - 0.4)) * (1.1 if '_bal_' in m else 1.0)
    return 2e-4


def fake(j):
    d = os.path.join(R, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    os.makedirs(d, exist_ok=True)
    m, B = j['method'], j['batch']
    Ks = (1, 2, 3)
    if j['shape'] == 'x64':
        ann = 1000.0
        cyc = {str(K): toy_x(m) * REF[str(K)] * ann for K in Ks}
        if m.startswith('abl_far_'):
            c = {'cnt': {str(K): dict(flips=0.3 * cyc[str(K)], tests=0.7 * cyc[str(K)], anneals=ann) for K in Ks}}
        elif m.startswith('abl_chord_'):
            c = {'cnt': {str(K): dict(flips=cyc[str(K)] - 256 * K * ann, steps=256 * K * ann, anneals=ann) for K in Ks}}
        else:
            c = {str(K): dict(flips=cyc[str(K)] - 256 * K * ann, steps=256 * K * ann, anneals=ann) for K in Ks}
    else:
        c = {} if m == 'mdichord32' else {'cnt': {str(K): dict(flips=100.0, tests=600.0, anneals=1.0) for K in Ks}}
    nb = j.get('n_batches') or 24
    b0 = j.get('first_batch', 0)
    p = toy_ber(m) * (0.8 if m.startswith('abl_far_') else 1.0) * 40
    for bi in range(b0, b0 + nb):
        be = (rng.random(B) < p).astype(np.uint8) * rng.integers(1, 30, B).astype(np.uint8)
        info = dict(cnt=c, bi=bi, method=m)
        np.savez(os.path.join(d, 'b%05d.npz' % bi), biterr=be, info=np.array(json.dumps(info)))
    uses = nb * B
    ber = toy_ber(m) * (1 + 0.05 * rng.random())
    json.dump(dict(ber=ber, vec_err=int(ber * uses * 10) + 1, uses=uses, seed=j['seed']), open(os.path.join(d, 'done.json'), 'w'))


def plan():
    o = subprocess.run([sys.executable, os.path.join(SRC, 'a519_plan.py'), R], capture_output=True, text=True, check=True)
    return json.load(open(os.path.join(R, 'plan.json')))['jobs'], json.load(open(os.path.join(R, 'select.json'))), o.stdout.split()


ran, it = [], 0
while True:
    jobs, sel, out = plan()
    it += 1
    if it == 1:
        sets = [j['set'] for j in jobs]
        check(sum(s == 'tunea' for s in sets) == 62, 'first plan: 62 stage-A cells')
        check(sum(s == 'calib' for s in sets) == 11, 'first plan: 11 calibration cells')
        check(not any(s == 'tuneb' for s in sets), 'no stage B before stage A')
        check(sum(s.startswith('h4_') for s in sets) == 120 and sum(s.startswith('h1_') for s in sets) == 30, 'first plan: C0/A64 and P1 chunks')
    order = {'tunea': 0, 'tuneb': 1, 'calib': 2}
    ks = [order.get(j['set'], 3) for j in jobs]
    check(ks == sorted(ks), 'queue order tunea < tuneb < calib < held-out (iteration %d)' % it)
    for j in jobs:
        s = j['set']
        if s == 'tunea':
            check(j['seed'] == 1000 and j['n_batches'] == 8 and j['batch'] == 500, 'stage A size/seed')
        elif s == 'tuneb':
            check(j['seed'] == 1010 and j['min_vec'] == 30 and j['max_bits'] == 20000 * 256, 'stage B size/seed')
        elif s == 'calib':
            check(j['seed'] == 1000 and j['first_batch'] == 50 and j['n_batches'] == 1 and j['batch'] == 500, 'calibration batch')
        else:
            check(j['seed'] == 2028, 'held-out seed 2028')
            if sel['pick'] is None:
                check(j['method'] in ('a56_128_0.3_0.3_0.4_0_alt_8', 'abl_far_64_0.1_0.1_0_bal_8', 'mdichord32', 'abl_far_64_0.1_0.1_0_rand_32'),
                      'held-out arm before the pick: %s' % j['method'])
            if j['method'] == 'a56_128_0.3_0.3_0.4_0_alt_8':
                check(j.get('stream') == 'mdichord8', 'C0 stream mdichord8')
    if out[2] == '1':
        break
    if not jobs:
        fails.append('stalled: no jobs and held-out not done'); break
    stage = min(order.get(j['set'], 3) for j in jobs)
    for j in jobs:
        if order.get(j['set'], 3) == stage:
            fake(j); ran.append(j)
    if it > 60:
        fails.append('too many iterations'); break

sel = json.load(open(os.path.join(R, 'select.json')))
print('corner rounds:', sel['corner_rounds'])
print('top3:', sel['top3'], 'pick:', sel['pick'])
print('S grid:', sel['S_grid'], 'S*:', sel['S_star'], 'x(pick) %.3f' % sel['calib_x'][sel['pick']])
check(sel['pick'] is not None and sel['pick'] in sel['top3'], 'pick from stage B top 3')
xs = {int(k.split('_')[2]): v for k, v in sel['calib_x'].items() if k.startswith('abl_far_')}
xc = sel['calib_x'][sel['pick']]
ok = [S for S in sel['S_grid'] if xs[S] <= xc]
check(sel['S_star'] == max(ok) and xs[max(sel['S_grid'])] > xc and xs[min(sel['S_grid'])] <= xc, 'S* rule and brackets')
for tag, n, arms in (('h4', 600, sel['held4'].values()), ('h1', 150, sel['held1'].values())):
    for m in arms:
        cov = sorted(j['first_batch'] + i for j in ran if j['set'].startswith(tag + '_') and j['method'] == m for i in range(j['n_batches']))
        check(cov == list(range(n)), 'coverage %s %s' % (tag, m))
check(len(sel['held4']) == 4, 'four P4 arms')
a = subprocess.run([sys.executable, os.path.join(SRC, 'analyze_a519.py'), R, os.path.join(R, 'analysis.json')], capture_output=True, text=True,
                   env=dict(os.environ, PYTHONPATH=SRC))
print(a.stdout, a.stderr[-2000:])
check(a.returncode == 0, 'analysis runs')
an = json.load(open(os.path.join(R, 'analysis.json')))
P4C = ('primary_Astar_C64', 'A64_C0', 'C64_C0', 'Astar_C0', 'Astar_A64')
check(all(an['P4'][k]['batches'] == 600 and not an['P4'][k]['partial'] for k in P4C) and an['P1']['A16_C0']['batches'] == 150
      and not an['P1']['A16_C0']['partial'], 'analysis pairs every batch, nothing partial')
xa = an['P4']['x']
check(abs(xa['C0']['x_F'] - 1) < 1e-9 and abs(xa['C0']['x'] - 1) < 1e-9, 'C0 x = 1')
check(abs(xa['Astar']['x'] - xs[sel['S_star']]) < 1e-9, 'A* held-out x = toy x')
check(abs(an['P4']['astar_over_c64_cycles'] - xs[sel['S_star']] / xc) < 1e-9, 'A*/C64 cycles on the primary pair')
# partial run (time cut): A* keeps batches 0-36, A64 the first 5 of every chunk, P1 A16 batches 0-19 (skipped if A* = A64)
import glob as G
SAME = sel['held4']['Astar'] == sel['held4']['A64']
for k, keep in (('Astar', lambda b: b < 37), ('A64', lambda b: b % 10 < 5)):
    for f in G.glob(os.path.join(R, 'h4_c*', 'x64', sel['held4'][k], 'snr_22.00', 'b*.npz')) if not SAME else []:
        if not keep(int(os.path.basename(f)[1:6])):
            os.remove(f)
for f in G.glob(os.path.join(R, 'h1_c*', 'x16', sel['held1']['A16'], 'snr_20.00', 'b*.npz')):
    if int(os.path.basename(f)[1:6]) >= 20:
        os.remove(f)
a = subprocess.run([sys.executable, os.path.join(SRC, 'analyze_a519.py'), R, os.path.join(R, 'analysis.json')], capture_output=True, text=True,
                   env=dict(os.environ, PYTHONPATH=SRC))
print(a.stdout, a.stderr[-2000:])
check(a.returncode == 0, 'partial analysis runs')
an = json.load(open(os.path.join(R, 'analysis.json')))
want = dict(primary_Astar_C64=37, A64_C0=300, C64_C0=600, Astar_C0=37, Astar_A64=20)
if SAME:
    want = dict(primary_Astar_C64=600, A64_C0=600, C64_C0=600, Astar_C0=600, Astar_A64=600)
check(all(an['P4'][k]['batches'] == n and an['P4'][k]['partial'] == (n < 600) for k, n in want.items()), 'partial pairing per comparison')
check((SAME or an['P4']['primary_Astar_C64']['last'] == 36) and an['P1']['A16_C0']['batches'] == 20 and an['P1']['A16_C0']['partial'], 'partial P1')
check(an['P4']['x']['Astar']['batches_with_C0'] == (600 if SAME else 37) and abs(an['P4']['x']['Astar']['x_F'] - xs[sel['S_star']]) < 1e-9, 'partial x_F')
for k in ('A64_C0',):
    c = an['P4'][k]
    if c['lo'] <= 1 <= c['hi']:
        check(c['term'] == ('inconclusive (partial run)' if c['lo'] <= 0.783 <= c['hi'] else 'no detected difference'), 'inconclusive rule')
print('ITERATIONS', it, 'JOBS', len(ran))
print('SIM PASS' if not fails else 'SIM FAIL: ' + '; '.join(sorted(set(fails))))
shutil.rmtree(T)
