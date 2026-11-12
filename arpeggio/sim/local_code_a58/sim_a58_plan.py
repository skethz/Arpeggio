#!/usr/bin/env python3
"""Synthetic run of a58_plan.py to the end (no GPU): fakes done.json and one batch file with counters for every queued job, with BER and flips
from a toy model, and checks that the plan reaches the held-out chunks with seeds, sizes and order as PROTOCOL_A58 says."""
import json, os, shutil, subprocess, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LATE = len(sys.argv) > 1 and sys.argv[1] == 'late'
ENV = dict(os.environ, A58_NOW=str(1794157200 + 1 if LATE else 1794000000))
R = tempfile.mkdtemp(prefix='sim_a58_')
rng = np.random.default_rng(0)


def fake(j):
    d = os.path.join(R, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    os.makedirs(d, exist_ok=True)
    m = j['method']
    if m.startswith('a56_'):
        cnt = {str(K): dict(flips=[124, 388, 1248][K - 1] * 1000.0, steps=0, anneals=1000.0) for K in (1, 2, 3)}
        ber = 3.5e-4
    else:
        a = m.split('_'); S, T0, st = int(a[2]), float(a[3]), a[7]
        N = {1: 256, 2: 512, 3: 768}
        cnt = {'cnt': {str(K): dict(flips=(N[K] / 2 * (0.3 if st == 'bal' else 1) + S * 2 * T0 * K) * 100.0,
                                    tests=(S * 2 * K + N[K] / 3) * 100.0, anneals=100.0, N=N[K]) for K in (1, 2, 3)}}
        ber = 1e-3 / (1 + S / 32) * (1 + abs(np.log(T0 / 0.1))) * (1 + rng.random() * 0.1)
    info = dict(cnt=cnt, bi=0, method=m)
    np.savez(os.path.join(d, 'b00000.npz'), biterr=np.zeros(1, np.uint8), info=np.array(json.dumps(info)))
    uses = 4000 if j['set'] != 'tuneb' else 12000
    json.dump(dict(ber=ber, vec_err=int(ber * uses * 256 / 10) + 1, uses=uses), open(os.path.join(d, 'done.json'), 'w'))


seenjobs, rounds = [], 0
while True:
    out = subprocess.run([sys.executable, os.path.join(HERE, 'a58_plan.py'), R], capture_output=True, text=True, env=ENV)
    assert out.returncode == 0, out.stderr
    plan = json.load(open(os.path.join(R, 'plan.json')))['jobs']
    if not plan:
        break
    rounds += 1
    assert rounds < 50, 'no end'
    for j in plan:
        seenjobs.append(j)
        fake(j)
sel = json.load(open(os.path.join(R, 'select.json')))
sets = [j['set'] for j in seenjobs]
held = [j for j in seenjobs if j['set'].startswith('held')]
assert seenjobs[0]['method'].startswith('a56_') and seenjobs[0]['stream'] == 'mdiane8' and seenjobs[0]['seed'] == 1000
assert all(j['seed'] == 1000 for j in seenjobs if j['set'] in ('tunea', 'probe'))
assert all(j['seed'] == 1010 for j in seenjobs if j['set'] == 'tuneb')
assert len(held) == 12 and all(j['seed'] == 344 and j['batch'] == 500 and j['n_batches'] == 50 for j in held)
assert sorted(j['first_batch'] for j in held) == list(range(0, 600, 50))
assert len({j['method'] for j in held}) == 1 and held[0]['method'] == sel['pick']
assert sel['stage_a_x'][sel['pick']] <= 1.0
assert not any(j['set'] == 'tunea' and j['method'] in sum(sel['pruned'].values(), []) for j in seenjobs), 'pruned cell ran'
if LATE:
    assert not any(j['set'] == 'tunea' and j['method'].startswith(('abl_far_8_', 'abl_far_16_')) for j in seenjobs), 'cut 1'
    assert all(j['max_bits'] == 10000 * 256 for j in seenjobs if j['set'] == 'tuneb') and sel['stage_b_cap'] == 10000, 'cut 2'
else:
    assert all(j['max_bits'] == 20000 * 256 for j in seenjobs if j['set'] == 'tuneb')
first_held = min(i for i, j in enumerate(seenjobs) if j['set'].startswith('held'))
assert all(j['set'] != 'tuneb' for j in seenjobs[first_held:]), 'held-out before stage B ended'
print('SIM PASS', 'late' if LATE else 'on time', 'rounds', rounds, 'jobs', len(seenjobs), {s: sets.count(s) for s in sorted(set(sets))}, 'pick', sel['pick'],
      'pruned', {k: len(v) for k, v in sel['pruned'].items()}, 'corners', sel['corner'])
shutil.rmtree(R)
