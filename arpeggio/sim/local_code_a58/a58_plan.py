#!/usr/bin/env python3
"""A5.8 plan and selection (PROTOCOL_A58.md sections 4-6). Pure function of the saved results: writes ROOT/plan.json with every job that can
run now and ROOT/select.json with the picks so far. Re-run by the supervisor; safe to repeat. Adapted from a55_plan.py (P4 only, rule (2)
first-accept only, B = 1 only). Jobs run through src/trace_x64.py. Usage: a58_plan.py ROOT"""
import glob, json, os, sys, time
import numpy as np

ROOT = sys.argv[1]
P = dict(pt='P4', sh='x64', snr=22.0, Ns=8, B=500, bpu=256, Rmax=3)
REF, REF_STREAM = 'a56_128_0.3_0.3_0.4_0_alt_8', 'mdiane8'
SR = (8, 16, 32, 64, 128)
XPROBE, BUD = 1.25, 1.0
CUT1 = 1794157200                                                         # 8 Nov 2026 18:00 CET (section 9, cuts 1 and 2)
NOW = float(os.environ.get('A58_NOW', time.time()))
NA, NCHUNK, CHUNK = 8, 12, 50                                              # stage A batches; held-out chunks of 50 batches of 500


def cells_r():
    sc = [(T, T) for T in (0.05, 0.1, 0.2, 0.3, 0.5, 0.8)] + [(0.6, 0.1), (1.2, 0.1), (1.2, 0.2), (2.4, 0.1)]
    return [(a, b, q) for a, b in sc for q in (0.0, 0.2, 0.4)]


def name(S, c, st):
    return 'abl_far_%d_%g_%g_%g_%s_%d' % (S, c[0], c[1], c[2], st, P['Ns'])


def jdir(st, m):
    return os.path.join(ROOT, st, P['sh'], m, 'snr_%05.2f' % P['snr'])


def done(st, m):
    p = os.path.join(jdir(st, m), 'done.json')
    return json.load(open(p)) if os.path.exists(p) else None


def failed3(st, m):
    return len(glob.glob(os.path.join(jdir(st, m), 'failed.*.json'))) >= 3


def raw_counts(d):
    tot = {}
    for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
        c = json.loads(str(np.load(f, allow_pickle=False)['info'])).get('cnt', {})
        c = c.get('cnt', c)
        for K, v in c.items():
            t = tot.setdefault(str(K), dict(flips=0.0, tests=0.0, anneals=0.0))
            t['flips'] += float(v.get('flips', 0.0)); t['tests'] += float(v.get('tests', 0.0)); t['anneals'] += float(v.get('anneals', 0.0))
    return tot


def ref_cost():
    """L_K + F_K of (i) on tuning seed 1000 (job tunea); None until it is done."""
    if done('tunea', REF) is None:
        return None
    tot = raw_counts(jdir('tunea', REF))
    return {K: 256 * int(K) + v['flips'] / v['anneals'] for K, v in tot.items() if v['anneals']}


def x_of(d, rc):
    """Model F: mean over K of (tests + flips) / anneals over (i)'s L_K + F_K."""
    xs = [(v['tests'] + v['flips']) / v['anneals'] / rc[K] for K, v in raw_counts(d).items() if v['anneals'] and K in rc]
    return float(np.mean(xs)) if xs else None


def job(st, m, **kw):
    j = dict(set=st, shape=P['sh'], method=m, snr=P['snr'], batch=P['B'], point=P['pt'])
    j.update(kw)
    return j


plan, seen = [], set()
prev = json.load(open(os.path.join(ROOT, 'select.json'))) if os.path.exists(os.path.join(ROOT, 'select.json')) else {}
sel = dict(cut={}, stage_b_queued_at=prev.get('stage_b_queued_at'), ref_cost=None, per_s={}, per_s_budget={}, corner={}, pruned={}, probe_x={}, stage_a_x={}, pool=[], stage_b=[], pick=None, held=None)


def add(j):
    k = (j['set'], j['method'])
    if k not in seen and done(*k) is None and not failed3(*k):
        seen.add(k)
        plan.append(j)


def survive(S, c, st, rc):
    """None while unknown, else whether the cell runs (probe mean x_F <= 1.25; S probed only if the cell survived at S / 2)."""
    if S >= 32:
        r = survive(S // 2, c, st, rc)
        if r is not True:
            return r
    m = name(S, c, st)
    if done('probe', m) is None:
        add(job('probe', m, seed=1000, batch=100, n_batches=1))
        return None
    x = x_of(jdir('probe', m), rc)
    sel['probe_x'][m] = x
    return x is None or x <= XPROBE


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


def stage_a(m):
    return job('tunea', m, seed=1000, n_batches=NA)


def finish_S(S, rc):
    """Stage A and corners for one S. Returns [(cell, start, method, result, x)] once complete, else None. Corners extend the per-S pick among
    cells within budget (x_F <= 1); the per-S pick over all cells is also reported."""
    res, missing = [], False
    for c in cells_r():
        for st in ('rand', 'bal'):
            m = name(S, c, st)
            if S >= 16:
                r = survive(S, c, st, rc)
                if r is None:
                    missing = True
                    continue
                if r is False:
                    sel['pruned'].setdefault(str(S), []).append(m)
                    continue
            d = done('tunea', m)
            if d is None:
                if S <= 16 and NOW > CUT1 and not os.path.isdir(jdir('tunea', m)):
                    sel['cut'].setdefault(str(S), []).append(m)
                    continue
                add(stage_a(m)); missing = True
            else:
                res.append((c, st, m, d, x_of(jdir('tunea', m), rc)))
    if missing:
        return None
    if not res:
        return []
    known = set(cells_r())
    for rnd in range(2):
        el = [t for t in res if t[4] is not None and t[4] <= BUD]
        if not el:
            break
        c, st, m, d, x = min(el, key=lambda t: rank(t[3], t[2]))
        nxt = [t for t in edge_steps(c, known) if t not in known]
        if not nxt:
            break
        wait = False
        for t in nxt:
            known.add(t)
            mt = name(S, t, st)
            dt = done('tunea', mt)
            if dt is None:
                add(stage_a(mt)); wait = True
            else:
                res.append((t, st, mt, dt, x_of(jdir('tunea', mt), rc)))
        if wait:
            return None
    best = min(res, key=lambda t: rank(t[3], t[2]))
    sel['per_s'][str(S)] = dict(method=best[2], ber=best[3]['ber'], vec_err=best[3]['vec_err'], uses=best[3]['uses'], x_F=best[4])
    el = [t for t in res if t[4] is not None and t[4] <= BUD]
    if el:
        b = min(el, key=lambda t: rank(t[3], t[2]))
        sel['per_s_budget'][str(S)] = dict(method=b[2], ber=b[3]['ber'], vec_err=b[3]['vec_err'], uses=b[3]['uses'], x_F=b[4])
        if edge_steps(b[0], known):
            sel['corner'][str(S)] = dict(method=b[2])
    return res


rc = ref_cost()
complete_a = False
if rc is None:
    add(job('tunea', REF, stream=REF_STREAM, seed=1000, n_batches=NA))
else:
    sel['ref_cost'] = rc
    ready = {S: finish_S(S, rc) for S in SR}
    complete_a = all(v is not None for v in ready.values())
    if complete_a:
        pool = [t for S in SR for t in ready[S] if t[4] is not None and t[4] <= BUD]
        for t in pool:
            sel['stage_a_x'][t[2]] = t[4]
        top = sorted(pool, key=lambda t: rank(t[3], t[2]))[:3]
        sel['pool'] = [dict(method=t[2], ber=t[3]['ber'], vec_err=t[3]['vec_err'], uses=t[3]['uses'], x_F=t[4]) for t in top]
        rs, wait = [], False
        if top and sel['stage_b_queued_at'] is None:
            sel['stage_b_queued_at'] = NOW
        capb = 10000 if (sel['stage_b_queued_at'] or NOW) > CUT1 else 20000
        sel['stage_b_cap'] = capb
        for t in top:
            d = done('tuneb', t[2])
            if d is None:
                add(job('tuneb', t[2], seed=1010, min_vec=30, min_bit=0, min_uses=0, max_bits=capb * P['bpu'])); wait = True
            else:
                rs.append((d['ber'], d['vec_err'] / d['uses'], t[2], d))
        if top and not wait:
            sel['stage_b'] = [dict(method=r[2], ber=r[0], vec_err=r[3]['vec_err'], uses=r[3]['uses']) for r in sorted(rs)]
            pick = min(rs)[2]
            sel['pick'] = pick
            sel['held'] = ['held%d' % c for c in range(NCHUNK)]
            for c in range(NCHUNK):
                add(job('held%d' % c, pick, seed=344, first_batch=CHUNK * c, n_batches=CHUNK))
sel['complete_a'] = complete_a
held_done = sel['pick'] is not None and all(done('held%d' % c, sel['pick']) is not None for c in range(NCHUNK))
sel['held_done'] = held_done


def order(j):
    s = j['set']
    stage = {'tunea': 0 if j['method'] == REF else 2, 'probe': 1, 'tuneb': 3}.get(s, 4)
    S = int(j['method'].split('_')[2]) if j['method'].startswith('abl_far_') else 0
    return (stage, -S, j['method'])                                       # long cells first inside a stage, so the stage ends evenly


plan.sort(key=order)
out = dict(host='hostB', amendment='A5.8 exploratory', jobs=plan)
for fn, obj in (('plan.json', out), ('select.json', sel)):
    tmp = os.path.join(ROOT, fn + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, os.path.join(ROOT, fn))
start = 0
for j in plan:
    cl = os.path.join(jdir(j['set'], j['method']), 'claim.json')
    if not os.path.exists(cl):
        start += 1
    else:
        try:
            start += not os.path.exists('/proc/%d' % int(json.load(open(cl))['pid']))
        except Exception:
            pass
print(len(plan), start, int(held_done))
