#!/usr/bin/env python3
"""A5.20 plan and selection. Pure function of saved results: writes ROOT/plan.json (every job that can
run now, in queue order) and ROOT/select.json. Re-run by the supervisor every 120 s; safe to repeat.
Needs ROOT/counts_a520.json (S2, gates passed). S*_k: largest S on the step-8 grid with calibration x(S) <= x_k(C64), same batch
(seed 1000, index 50, 500 uses); x(S) from A5.19's hostB calibration (S = 96..488) or from new calibration jobs in ROOT/calib
(downward steps; the next DOWN steps are queued at once, values beyond the stopping point unused).
Held-out: seed 2028, batches 0-599 x 500 uses, chunks of 10, interleaved by chunk index (k = 2, 4, inf). Usage: a520_plan.py ROOT"""
import glob, json, os, sys
import numpy as np
ROOT = sys.argv[1]
A19CAL = '<SCRATCH>/arpeggio_ber_20261024/a519m/results/a519/calib'
REF4 = {str(k): float(v) for k, v in json.load(open('<SCRATCH>/arpeggio_ber_20261024/results/a58/select.json'))['ref_cost'].items()}
HSEED, N4, CH4, B4 = 2028, 600, 10, 500
GRID_LO, GRID_HI, STEP, SMIN, DOWN = 96, 488, 8, 8, 4
KS = (('2', 'c2'), ('4', 'c4'), ('inf', 'cinf'))
REUSE = {64: 'abl_far_64_0.1_0.1_0_bal_8', 480: 'abl_far_480_0.1_0.1_0_bal_8'}   # A5.19 arms A64, A* (copied to ref/)


def far(S):
    return 'abl_far_%d_0.1_0.1_0_bal_8' % S


def jdir(root, st, m):
    return os.path.join(root, st, 'x64', m, 'snr_22.00')


def x_of(d):
    """Mean over K of (tests or steps + flips) / anneals over A5.8 ref_cost (as A5.19's planner)."""
    tot = {}
    for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
        c = json.loads(str(np.load(f, allow_pickle=False)['info'])).get('cnt', {})
        c = c.get('cnt', c)
        for K, v in c.items():
            if K.startswith('_'):
                continue
            t = tot.setdefault(str(K), dict(work=0.0, flips=0.0, anneals=0.0))
            t['work'] += float(v.get('tests', v.get('steps', 0.0))); t['flips'] += float(v.get('flips', 0.0)); t['anneals'] += float(v.get('anneals', 0.0))
    xs = [(v['work'] + v['flips']) / v['anneals'] / REF4[K] for K, v in tot.items() if v['anneals'] and K in REF4]
    return float(np.mean(xs)) if xs else None


def done(d):
    return os.path.exists(os.path.join(d, 'done.json'))


def failed3(d):
    return len(glob.glob(os.path.join(d, 'failed.*.json'))) >= 3


plan, seen = [], set()


def add(j):
    k = (j['set'], j['method'])
    d = jdir(ROOT, j['set'], j['method'])
    if k not in seen and not done(d) and not failed3(d):
        seen.add(k); plan.append(j)


def job(st, m, **kw):
    j = dict(set=st, shape='x64', method=m, snr=22.0, batch=B4, point='P4'); j.update(kw); return j


def xcal(S):
    """x(S) on the calibration batch: A5.19's hostB calibration if it has S, else this run's calib job (queued if missing)."""
    d19 = jdir(os.path.dirname(A19CAL), 'calib', far(S))
    if GRID_LO <= S <= GRID_HI and done(d19):
        return x_of(d19)
    d = jdir(ROOT, 'calib', far(S))
    if done(d):
        return x_of(d)
    add(job('calib', far(S), seed=1000, first_batch=50, n_batches=1))
    return None


sel = dict(x_k=None, S_star={}, arms={}, calib_x={}, held_done=False)
cf = os.path.join(ROOT, 'counts_a520.json')
cn = json.load(open(cf)) if os.path.exists(cf) else None
if cn and cn.get('done') and all(cn['gates']['G1_G3'].values()) and cn['gates']['G2'] and cn['gates']['G2x']:
    sel['x_k'] = cn['x_k']
    for k, key in KS:
        t = cn['x_k'][key]
        x96 = xcal(GRID_LO)
        if x96 is None:
            continue
        S_star = None
        if x96 <= t:                                                     # upward from 96
            S = GRID_LO
            while True:
                x = xcal(S)
                sel['calib_x'][far(S)] = x
                if x is None or x > t:
                    S_star = S - STEP if x is not None else None
                    break
                if S == GRID_HI:                                         # extension upward (not expected: x(488) > x_1(C64))
                    xcal(S + STEP); break
                S += STEP
        else:                                                            # downward from 88, DOWN steps queued at once
            S = GRID_LO - STEP
            while S >= SMIN:
                for s2 in range(S, max(SMIN, S - STEP * (DOWN - 1)) - 1, -STEP):
                    xcal(s2)
                x = xcal(S)
                sel['calib_x'][far(S)] = x
                if x is None:
                    break
                if x <= t:
                    S_star = S; break
                S -= STEP
        if S_star is not None:
            sel['S_star'][k] = S_star
            sel['arms'][k] = REUSE.get(S_star, far(S_star))
    # held-out chunks, interleaved by chunk index across arms (k = 2, 4, inf), reused A5.19 arms excluded
    arms = []
    for k, _ in KS:
        m = sel['arms'].get(k)
        if m and m not in REUSE.values() and m not in arms:
            arms.append(m)
    for c in range(N4 // CH4):
        for m in arms:
            add(job('h4_c%03d' % c, m, seed=HSEED, first_batch=CH4 * c, n_batches=CH4))
    sel['held_done'] = len(sel['S_star']) == len(KS) and all(
        done(jdir(ROOT, 'h4_c%03d' % c, m)) for m in arms for c in range(N4 // CH4))
plan.sort(key=lambda j: j['set'] != 'calib')                             # calibration first (stable)
for name, obj in (('plan.json', dict(host='hostB', experiment='A5.20', jobs=plan)), ('select.json', sel)):
    p = os.path.join(ROOT, name)
    with open(p + '.tmp', 'w') as f:
        json.dump(obj, f, indent=1)
    os.replace(p + '.tmp', p)
print('plan %d jobs; x_k %s; S* %s; held_done %s' % (len(plan), sel['x_k'] and {k: round(v, 4) for k, v in sel['x_k'].items()},
                                                    sel['S_star'], sel['held_done']))
