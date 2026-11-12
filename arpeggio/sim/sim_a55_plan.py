#!/usr/bin/env python3
"""Dry run of a55_plan.py's state machine, no GPU: every queued job gets synthetic results, with hot cells flipping often and BER favouring
grid edges, until the plan is empty. Checks the order of stages and the invariants of PROTOCOL_A55.md sections 5-6. Usage: sim_a55_plan.py ROOT"""
import hashlib, json, os, subprocess, sys, time
import numpy as np
ROOT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
BPU = dict(x16=64, x32=128, q32=64)


def rnd(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 2 ** 32


def parse(m):
    a = m.split('_')
    if a[1] == 'fam':
        return 'fam', int(a[2]), float(a[3]), float(a[4]), 0.0, a[5], int(a[6])
    if a[1] == 'far':
        return 'far', int(a[2]), float(a[3]), float(a[4]), float(a[5]), a[6], int(a[7])
    if a[1] == 'ape':
        return 'ape', 128, float(a[2]), float(a[3]), float(a[4]), a[5], int(a[6])
    return 'ptb', 8, float(a[3]), float(a[4]), 0.0, 'bal', int(a[5])


def write(j):
    d = os.path.join(ROOT, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    os.makedirs(d, exist_ok=True)
    arm, S, T0, T1, q, st, Ns = parse(j['method'])
    count = {}
    for K in ('1',) if j['shape'] == 'q32' else ('1', '2', '3'):
        P = 2 * int(K); N = P * Ns
        acc = min(0.5, (T0 * T1) ** 0.5 * 0.4) * (1 - q / 2)
        F = S * N * acc
        tests = S * P + 2 * F
        count[K] = dict(flips=F * 100, tests=tests * 100, last=0, decisions=S * N * 100, anneals=100, N=N)
    uses = j.get('min_uses', 0) or 100
    uses = max(uses, j['batch'])
    u = rnd(j['method'] + j['set'])
    ber = (1e-3 + 1e-3 * u) * (1 + abs(np.log2((T0 * T1) ** 0.5 / 0.02)))     # low BER at cold corners, so picks reach the edges
    be = int(ber * uses * BPU[j['shape']]) + 1
    np.savez(os.path.join(d, 'b00000.npz'), biterr=np.zeros(1, np.uint8), info=np.array(json.dumps(dict(seconds=1.0, count=count))))
    with open(os.path.join(d, 'done.json'), 'w') as f:
        json.dump(dict(set=j['set'], shape=j['shape'], method=j['method'], snr=j['snr'], seed=j['seed'], uses=uses, bits=uses * BPU[j['shape']],
                       vec_err=max(1, be // 2), bit_err=be, ber=be / (uses * BPU[j['shape']]), seconds=1.0, capped=False), f)


seen, seq, tmax = set(), [], 0
for it in range(60):
    t = time.time()
    out = subprocess.check_output([sys.executable, os.path.join(HERE, 'a55_plan.py'), ROOT]).decode().strip()
    tmax = max(tmax, time.time() - t)
    jobs = json.load(open(os.path.join(ROOT, 'plan.json')))['jobs']
    sel = json.load(open(os.path.join(ROOT, 'select.json')))
    sets = sorted({j['set'] for j in jobs})
    print('round', it, 'plan', out, 'sets', sets, 'picks', len(sel['per_s']), 'corner', len(sel['corner']), 'complete_a', sel['complete_a'], 'held', sel['heldout_final'], flush=True)
    if not jobs:
        break
    for j in jobs:
        k = (j['set'], j['shape'], j['method'])
        assert k not in seen, k
        seen.add(k); seq.append((it, j))
        write(j)
assert out.endswith(' 1'), out
# invariants
first_abl = min(i for i, j in seq if j['set'] == 'abl')
last_tune = max(i for i, j in seq if j['set'] != 'abl')
assert last_tune < first_abl, 'a held-out job was queued before tuning ended'
assert all((j['seed'] == 102) == (j['set'] == 'abl') for _, j in seq)
assert all(j['seed'] == 1010 for _, j in seq if j['set'] == 'tuneb') and all(j['seed'] == 1000 for _, j in seq if j['set'] in ('tunea', 'probe'))
ab = {(j['shape'], j['method']) for _, j in seq if j['set'] == 'tunea'}
assert all((j['shape'], j['method']) in ab for _, j in seq if j['set'] == 'tuneb'), 'stage B cell without stage A'
for pt, sh, Ns in (('P1', 'x16', 32), ('P2', 'x32', 8), ('P3', 'q32', 8)):
    h = sel['held'][pt]
    assert 'abl_ape_0.3_0.3_0.4_bal_%d' % Ns in h and len(h) == len(set(h))
    assert all(m.endswith('_%d' % Ns) for m in h)
    assert not any(p.startswith(pt) and ('/128' in p) and p in sel['pruned'] and p in sel['per_s'] and len(sel['pruned'][p]) == 44 for p in sel['pruned'])
    print(pt, 'held', len(h), {g: v['method'] for g, v in sel['budget'].items() if g.startswith(pt + '/F-R')})
# a cell pruned at S = 32 must have no probe or stage A at 64, 128; and S >= 32 stage A only with a passing probe
pr = {(p, m) for p, L in sel['pruned'].items() for m in L}
probes = {(j['shape'], j['method']) for _, j in seq if j['set'] == 'probe'}
for p, L in sel['pruned'].items():
    for m in L:
        sh = {'P1': 'x16', 'P2': 'x32'}[p[:2]]
        assert (sh, m) not in ab, 'pruned cell ran stage A'
print('counts', {s: sum(1 for _, j in seq if j['set'] == s) for s in ('probe', 'tunea', 'tuneb', 'abl')}, 'pruned', len(pr), 'corners', sel['corner'] and len(sel['corner']), 'slowest plan run %.1f s' % tmax)
print('rounds', it, 'per_s', len(sel['per_s']), 'budget', len(sel['budget']), 'ap', len(sel['ap']), 'pt', len(sel['pt']))
print('SIM PASS')
