#!/usr/bin/env python3
"""A5.19 plan and selection. Pure function of the saved results: writes ROOT/plan.json (every job that
can run now, in queue order) and ROOT/select.json (picks so far). Re-run by the supervisor every 120 s; safe to repeat.
Jobs run through src/trace_a514.py (trace_a56.py with x64 and arpx514 registered).
Parts: (1) Chord re-tune at P4 as in A5.5 (31 cells x 2 starts, corners, top 3 to stage B); (2) S* for Arpeggio (T 0.1, q 0,
bal) at the re-tuned Chord's calibrated cycles, rule as in A5.15; (3) held-out on fresh seed 2028 at P4 (C0, C64, A*, A64) and
P1 (C0, A16), fixed length, interleaved. Usage: a519_plan.py ROOT  (ROOT = .../results/a519)"""
import glob
import json
import os
import sys

import numpy as np

ROOT = sys.argv[1]
RES = os.path.dirname(os.path.abspath(ROOT))
P4 = dict(pt='P4', sh='x64', snr=22.0, Ns=8, B=500, bpu=256)
P1 = dict(pt='P1', sh='x16', snr=20.0, Ns=32, B=2000, bpu=64)
HSEED = 2028
C0_4, C0_4_STREAM = 'a56_128_0.3_0.3_0.4_0_alt_8', 'mdichord8'             # default Chord at P4, as X64F (seed 344)
A64 = 'abl_far_64_0.1_0.1_0_bal_8'                                         # the paper's 64-user Arpeggio (A5.8 B = 1 pick)
C0_1, A16 = 'mdichord32', 'abl_far_64_0.1_0.1_0_rand_32'                     # default (= A5.5 re-tuned) Chord and Arpeggio at P1
NA, CAPB = 8, 20000                                                        # stage A 8 x 500 uses (seed 1000); stage B cap (seed 1010)
SGRID0, SSTEP, SMIN = tuple(range(96, 177, 8)), 8, 8                       # first S window for the S* rule, step 8
N4, CH4, N1, CH1 = 600, 10, 150, 10                                        # held-out batch indices and chunk sizes
REF4 = {str(k): float(v) for k, v in json.load(open(os.path.join(RES, 'a58', 'select.json')))['ref_cost'].items()}


def cells_a():
    """A5.5 Chord grid: 31 cells (T0, T1, q)."""
    return [(T, T, q) for q in (0.0, 0.1, 0.2, 0.4, 0.8) for T in (0.1, 0.15, 0.2, 0.3, 0.5)] + \
           [(a, b, q) for a, b in ((0.6, 0.2), (0.6, 0.1), (1.2, 0.2)) for q in (0.2, 0.4)]


def chord(c, st):
    return 'abl_chord_%g_%g_%g_%s_%d' % (c[0], c[1], c[2], st, P4['Ns'])


def far(S):
    return 'abl_far_%d_0.1_0.1_0_bal_%d' % (S, P4['Ns'])


def jdir(st, p, m):
    return os.path.join(ROOT, st, p['sh'], m, 'snr_%05.2f' % p['snr'])


def done(st, p, m):
    f = os.path.join(jdir(st, p, m), 'done.json')
    return json.load(open(f)) if os.path.exists(f) else None


def failed3(st, p, m):
    return len(glob.glob(os.path.join(jdir(st, p, m), 'failed.*.json'))) >= 3


def counts(d):
    tot = {}
    for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
        c = json.loads(str(np.load(f, allow_pickle=False)['info'])).get('cnt', {})
        c = c.get('cnt', c)
        for K, v in c.items():
            t = tot.setdefault(str(K), dict(work=0.0, flips=0.0, anneals=0.0))
            t['work'] += float(v.get('tests', v.get('steps', 0.0))); t['flips'] += float(v.get('flips', 0.0))
            t['anneals'] += float(v.get('anneals', 0.0))
    return tot


def x_of(d):
    """Mean over K of (tests or steps + flips) / anneals over default Chord's L_K + F_K on seed 1000 (A5.8 ref_cost)."""
    xs = [(v['work'] + v['flips']) / v['anneals'] / REF4[K] for K, v in counts(d).items() if v['anneals'] and K in REF4]
    return float(np.mean(xs)) if xs else None


def rank(d, m):
    return (d['ber'], d['vec_err'] / d['uses'], m)


def edge_steps(c, grid):
    """As a55_plan.edge_steps: next cells beyond a grid edge, other settings held."""
    T0, T1, q = c
    steps = []
    if T0 == T1:
        v = [a for a, b, _ in grid if a == b]
        if T0 == max(v):
            steps.append(lambda t: (t[0] * 2, t[1] * 2, t[2]))
        if T0 == min(v):
            steps.append(lambda t: (t[0] / 2, t[1] / 2, t[2]))
    else:
        v0 = [a for a, b, _ in grid if a != b]
        v1 = [b for a, b, _ in grid if a != b]
        if T0 == max(v0):
            steps.append(lambda t: (t[0] * 2, t[1], t[2]))
        if T1 == min(v1):
            steps.append(lambda t: (t[0], t[1] / 2, t[2]))
    if q is not None and q > 0 and q == max(x[2] for x in grid):
        steps.append(lambda t: (t[0], t[1], t[2] * 2))
    out = [f(c) for f in steps]
    if len(steps) > 1:
        t = c
        for f in steps:
            t = f(t)
        out.append(t)
    return out


plan, seen = [], set()
sel = dict(ref_cost=REF4, stage_a={}, corner_rounds=[], corner_open=None, top3=[], stage_b=[], pick=None, calib_x={}, S_grid=None,
           S_star=None, astar=None, held4={}, held1={}, held_done=False)


def job(st, p, m, **kw):
    j = dict(set=st, shape=p['sh'], method=m, snr=p['snr'], batch=p['B'], point=p['pt'])
    j.update(kw)
    return j


def add(j, p):
    k = (j['set'], j['method'], p['pt'])
    if k not in seen and done(j['set'], p, j['method']) is None and not failed3(j['set'], p, j['method']):
        seen.add(k)
        plan.append(j)


def tunea(m):
    add(job('tunea', P4, m, seed=1000, n_batches=NA), P4)


# ---------------- (1) Chord re-tune at P4: stage A, corners (two rounds), stage B
res, missing = [], False
for c in cells_a():
    for st in ('rand', 'bal'):
        m = chord(c, st)
        d = done('tunea', P4, m)
        if d is None:
            tunea(m); missing = True
        else:
            res.append((c, st, m, d))
complete_a = False
if not missing:
    known = set(cells_a())
    wait = False
    for rnd in range(2):
        c, st, m, d = min(res, key=lambda t: rank(t[3], t[2]))
        nxt = [t for t in edge_steps(c, known) if t not in known]
        if not nxt:
            break
        sel['corner_rounds'].append(dict(round=rnd + 1, from_=m, added=[chord(t, st) for t in nxt]))
        for t in nxt:
            known.add(t)
            mt = chord(t, st)
            dt = done('tunea', P4, mt)
            if dt is None:
                tunea(mt); wait = True
            else:
                res.append((t, st, mt, dt))
        if wait:
            break
    if not wait:
        complete_a = True
        best = min(res, key=lambda t: rank(t[3], t[2]))
        if edge_steps(best[0], known):
            sel['corner_open'] = best[2]                                   # still on an edge after two rounds: reported
for c, st, m, d in res:
    sel['stage_a'][m] = dict(ber=d['ber'], vec_err=d['vec_err'], uses=d['uses'], x=x_of(jdir('tunea', P4, m)))
pick = None
if complete_a:
    top = sorted(res, key=lambda t: rank(t[3], t[2]))[:3]
    sel['top3'] = [t[2] for t in top]
    rs, wait = [], False
    for t in top:
        d = done('tuneb', P4, t[2])
        if d is None:
            add(job('tuneb', P4, t[2], seed=1010, min_vec=30, min_bit=0, min_uses=0, max_bits=CAPB * P4['bpu']), P4); wait = True
        else:
            rs.append((d['ber'], d['vec_err'] / d['uses'], t[2], d))
    if not wait:
        sel['stage_b'] = [dict(method=r[2], ber=r[0], vec_err=r[3]['vec_err'], uses=r[3]['uses']) for r in sorted(rs)]
        pick = min(rs)[2]
        sel['pick'] = pick


# ---------------- (2) S* calibration (seed 1000, batch index 50, 500 uses; A5.15 rule with step 8)
def calib(m):
    if done('calib', P4, m) is None:
        add(job('calib', P4, m, seed=1000, first_batch=50, n_batches=1), P4)
        return None
    return x_of(jdir('calib', P4, m))


for S in SGRID0:
    sel['calib_x'][far(S)] = calib(far(S))
astar = None
if pick is not None:
    xc = calib(pick)
    sel['calib_x'][pick] = xc
    if xc is not None:
        grid = list(SGRID0)
        while True:
            xs = {S: calib(far(S)) for S in grid}
            for S, v in xs.items():
                sel['calib_x'][far(S)] = v
            if any(v is None for v in xs.values()):
                break
            if xs[max(grid)] <= xc:
                grid.append(max(grid) + SSTEP); continue
            if xs[min(grid)] > xc and min(grid) - SSTEP >= SMIN:
                grid.insert(0, min(grid) - SSTEP); continue
            ok = [S for S in grid if xs[S] <= xc]
            sel['S_grid'] = grid
            if ok:
                sel['S_star'] = max(ok)
                astar = far(max(ok))
                sel['astar'] = astar
            else:
                sel['S_star'] = 'none: x(%d) > x(C64)' % min(grid)
            break


# ---------------- (3) held-out, seed 2028, fixed length, interleaved by chunk
def chunks(p, tag, m, n, ch, **kw):
    return [job('%s_c%03d' % (tag, c), p, m, seed=HSEED, first_batch=ch * c, n_batches=min(ch, n - ch * c), **kw)
            for c in range((n + ch - 1) // ch)]


arms4 = [('C0', C0_4, dict(stream=C0_4_STREAM)), ('A64', A64, {})]
if pick is not None:
    arms4.append(('C64', pick, {}))
if astar is not None:
    arms4.append(('Astar', astar, {}))
arms1 = [('C0', C0_1, {}), ('A16', A16, {})]
held = []
for i, (k, m, kw) in enumerate(arms4):
    sel['held4'][k] = m
    for c, j in enumerate(chunks(P4, 'h4', m, N4, CH4, **kw)):
        held.append(((c + 0.5) / (N4 / CH4), i, j, P4))
for i, (k, m, kw) in enumerate(arms1):
    sel['held1'][k] = m
    for c, j in enumerate(chunks(P1, 'h1', m, N1, CH1, **kw)):
        held.append(((c + 0.5) / (N1 / CH1), 10 + i, j, P1))
for _, _, j, p in sorted(held, key=lambda t: (t[0], t[1])):
    add(j, p)
hd = astar is not None and all(done(j['set'], p, j['method']) is not None for _, _, j, p in held)
sel['held_done'] = hd
sel['complete_a'] = complete_a


def order(j):
    s = j['set']
    return {'tunea': 0, 'tuneb': 1, 'calib': 2}.get(s, 3)


plan = sorted(enumerate(plan), key=lambda t: (order(t[1]), t[0]))         # stable: held-out keeps its interleaved order
plan = [j for _, j in plan]
out = dict(host='hostB', experiment='A5.19', jobs=plan)
for fn, obj in (('plan.json', out), ('select.json', sel)):
    tmp = os.path.join(ROOT, fn + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, os.path.join(ROOT, fn))
start = 0
for j in plan:
    p = P4 if j['shape'] == 'x64' else P1
    cl = os.path.join(jdir(j['set'], p, j['method']), 'claim.json')
    if not os.path.exists(cl):
        start += 1
    else:
        try:
            start += not os.path.exists('/proc/%d' % int(json.load(open(cl))['pid']))
        except Exception:
            pass
print(len(plan), start, int(hd))
