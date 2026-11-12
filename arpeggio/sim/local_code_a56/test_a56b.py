#!/usr/bin/env python3
"""A5.6 second set of checks: apx55 methods through the trace path; the planner and analysis on a small real run under a scratch root."""
import json, os, shutil, subprocess, sys
import numpy as np, torch
sys.argv = ['test_a56b', '--plan', 'x', '--root', 'x', '--worker', 'test']
torch.cuda.set_per_process_memory_fraction(0.25, 0)
import apx, a56lib as L, apx55
A = '<SCRATCH>/ap_ber_20261024'
ctx = apx.Ctx(json.load(open(A + '/results/tuned_a5.json')))
ok = True
def rep(n, c, e=''):
    global ok
    ok = ok and bool(c)
    print(('PASS ' if c else 'FAIL ') + n, e, flush=True)
for shape, snr, m, B in (('x16', 20.0, 'abl_fam_4_1.2_0.05_rand_32', 100), ('x32', 22.0, 'abl_ape_0.2_0.2_0.2_rand_8', 100), ('q32', 14.0, 'abl_far_8_0.3_0.3_0.2_bal_8', 400)):
    s = apx.SHAPES[shape]; c = s['mdi']
    b = apx.draw(1020, snr, 2, B, s['nt'], s['M'])
    z, _, _ = apx.mimo.mmse(b)
    g1 = torch.Generator(device='cuda'); g1.manual_seed(11)
    g2 = torch.Generator(device='cuda'); g2.manual_seed(11)
    s1 = {}; s2 = {}
    f1, tl1, Ns = apx55.solver_for(m, shape, g1, ctx, s1)
    lh1, _ = apx.mdi_diag(b, f1, Ns, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z, stats={}, to_levels=tl1)
    f2, tl2, Ns2 = L.solver_for(m, shape, g2, ctx, s2)
    lh2, tr = L.mdi_trace(b, f2, Ns2, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z, to_levels=tl2)
    rep('apx55 path %s' % m, torch.equal(lh1, lh2), json.dumps(s2.get('cnt', {}))[:120])
# planner and analysis on a scratch root holding one small tuning run and one held-out run
R = A + '/results/a56_dryrun/a56'
shutil.rmtree(os.path.dirname(R), ignore_errors=True)
os.makedirs(R)
for f in ('abl', 'a55', 'tab2'):
    os.symlink(A + '/results/' + f, os.path.dirname(R) + '/' + f)
print(subprocess.check_output(['python', A + '/src/make_plan_a56.py', R], text=True), end='')
pl = json.load(open(R + '/plan.json'))['jobs']
print('plan jobs', len(pl), 'first', pl[0]['set'], pl[0]['method'])
from collections import Counter
print(Counter(j['set'] for j in pl))
rep('plan unique dirs', len({(j['set'], j['shape'], j['method'], j['snr']) for j in pl}) == len(pl))
rep('replay job counts saved batches', [j for j in pl if j['set'] == 'R' and j['point'] == 'P1'][0]['n_batches'] == 10)
# one short job of each kind through the worker's main path
small = [dict(j) for j in pl if (j['set'], j['point']) in (('R', 'P3'),)][:1]
tun = dict([j for j in pl if j['set'] == 'A' and j['point'] == 'P3'][0], max_bits=8000 * 64, min_vec=0, min_bit=0, min_uses=8000)
arm = dict([j for j in pl if j['set'] == 'F' and j['point'] == 'P3'][0], max_bits=8000 * 64, min_vec=0, min_bit=0, min_uses=8000)
lane = dict([j for j in pl if j['set'] == 'L' and j['point'] == 'P3'][0], max_bits=8000 * 64, min_vec=0, min_bit=0, min_uses=8000)
json.dump(dict(jobs=small + [tun, arm, lane]), open(R + '/small.json', 'w'))
print(subprocess.check_output(['python', A + '/src/trace_a56.py', '--plan', R + '/small.json', '--root', R, '--worker', 'dry', '--mem', '0.25'], text=True, stderr=subprocess.STDOUT)[-900:], flush=True)
print(subprocess.check_output(['python', A + '/src/make_plan_a56.py', R], text=True), end='')
print(open(R + '/select.json').read()[:600])
print(subprocess.check_output(['python', A + '/src/analyze_a56.py', R], text=True), end='')
an = json.load(open(R + '/analysis.json'))
rep('analysis has P3 stop table', 'rows' in an['stop']['P3'].get('heldout', an['stop']['P3'].get('tuning', {})))
print(json.dumps(an['stop']['P3'].get('tuning', {}).get('rows', [])[:2])[:500])
print(subprocess.check_output(['python', A + '/src/a56_status.py', R], text=True))
shutil.rmtree(os.path.dirname(R), ignore_errors=True)
print('ALL PASS' if ok else 'FAIL', flush=True)
