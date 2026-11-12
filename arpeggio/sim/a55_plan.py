#!/usr/bin/env python3
"""A5.5 plan and selection (PROTOCOL_A55.md sections 5-6). Pure function of the saved results: writes ROOT/plan.json with every job
that can run now, and ROOT/select.json with the picks so far. Re-run by the supervisor; safe to repeat. Order inside one key: stage A,
then corners, then stage B, then held-out. Usage: a55_plan.py ROOT [--brief]"""
import glob, json, math, os, sys
import numpy as np

ROOT = sys.argv[1]
PT = {'P1': dict(sh='x16', snr=20.0, Ns=32, hmin=8000, B=2000, ta=4000, bpu=64),
      'P2': dict(sh='x32', snr=22.0, Ns=8, hmin=4000, B=1000, ta=2000, bpu=128),
      'P3': dict(sh='q32', snr=14.0, Ns=8, hmin=8000, B=4000, ta=None, bpu=64)}
PHI = json.load(open(os.path.join(os.path.dirname(os.path.abspath(ROOT)), 'tuned_a52.json')))['flip_phi']
SM = (1, 2, 3, 4, 8, 16, 32, 64, 128)
SR = (4, 8, 16, 32, 64, 128)
BUDGETS = (0.5, 1, 2, 3)
XMAX = 4.0


def ref_cost(sh, K):
    L = 128 * 2 * K
    return L + PHI[sh][str(K)] * L


def cells_m(S):
    if S == 1:
        return [(T, T, None) for T in (0.05, 0.1, 0.2, 0.3, 0.6, 1.2, 2.4)]
    g = [(a, b, None) for a in (0.15, 0.3, 0.6, 1.2, 2.4, 4.8) for b in (0.0125, 0.05, 0.15) if b < a]
    return g + [(T, T, None) for T in (0.05, 0.1, 0.2, 0.3, 0.6)]


def cells_r(S):
    sc = [(T, T) for T in (0.05, 0.1, 0.2, 0.3, 0.5, 0.8)] + [(0.6, 0.1), (1.2, 0.1), (1.2, 0.2), (2.4, 0.1)]
    return [(a, b, q) for a, b in sc for q in (0.0, 0.2, 0.4)]


def cells_a():
    return [(T, T, q) for q in (0.0, 0.1, 0.2, 0.4, 0.8) for T in (0.1, 0.15, 0.2, 0.3, 0.5)] + \
           [(a, b, q) for a, b in ((0.6, 0.2), (0.6, 0.1), (1.2, 0.2)) for q in (0.2, 0.4)]


def cells_p():
    return [(a, b) for a in (0.3, 0.6, 1.2, 2.4) for b in (0.05, 0.15, a)] + [(a, b) for a in (0.075, 0.15) for b in (0.0125, 0.025, 0.05)]


def name(arm, S, c, st, Ns):
    if arm == 'fam':
        return 'abl_fam_%d_%g_%g_%s_%d' % (S, c[0], c[1], st, Ns)
    if arm == 'far':
        return 'abl_far_%d_%g_%g_%g_%s_%d' % (S, c[0], c[1], c[2], st, Ns)
    return 'abl_ape_%g_%g_%g_%s_%d' % (c[0], c[1], c[2], st, Ns)


def jdir(st, sh, m, snr):
    return os.path.join(ROOT, st, sh, m, 'snr_%05.2f' % snr)


def done(st, sh, m, snr):
    p = os.path.join(jdir(st, sh, m, snr), 'done.json')
    return json.load(open(p)) if os.path.exists(p) else None


def failed3(st, sh, m, snr):
    return len(glob.glob(os.path.join(jdir(st, sh, m, snr), 'failed.*.json'))) >= 3


def counts(st, sh, m, snr):
    """Per K: F, tests per anneal, N from the batches' saved counters."""
    tot = {}
    for f in sorted(glob.glob(os.path.join(jdir(st, sh, m, snr), 'b*.npz'))):
        z = np.load(f, allow_pickle=False)
        for K, v in json.loads(str(z['info'])).get('count', {}).items():
            d = tot.setdefault(K, dict(flips=0.0, tests=0, anneals=0, N=v['N']))
            d['flips'] += v['flips']; d['tests'] += v.get('tests', 0); d['anneals'] += v['anneals']
    return {K: dict(F=v['flips'] / v['anneals'], tests=v['tests'] / v['anneals'], N=v['N']) for K, v in tot.items() if v['anneals']}


def x_of(cnt, sh, S, model):
    xs = []
    for K, v in cnt.items():
        c = S * v['N'] + v['F'] if model == 'E' else v['tests'] + v['F']
        xs.append(c / ref_cost(sh, int(K)))
    return float(np.mean(xs)) if xs else None


def job_a(pt, m):
    p = PT[pt]
    if p['ta'] is None:                                                    # P3: section 6's stopping rule on the tuning seed
        return dict(set='tunea', shape=p['sh'], method=m, snr=p['snr'], seed=1000, batch=p['B'], min_uses=p['hmin'], point=pt)
    return dict(set='tunea', shape=p['sh'], method=m, snr=p['snr'], seed=1000, batch=p['B'], min_vec=0, min_bit=0, min_uses=p['ta'],
                max_bits=p['ta'] * p['bpu'], point=pt)


def job_probe(pt, m):
    p = PT[pt]
    return dict(set='probe', shape=p['sh'], method=m, snr=p['snr'], seed=1000, batch=100, min_vec=0, min_bit=0, min_uses=100, max_bits=100 * p['bpu'], point=pt)


def job_b(pt, m):
    p = PT[pt]
    if p['ta'] is None:
        return dict(set='tuneb', shape=p['sh'], method=m, snr=p['snr'], seed=1010, batch=p['B'], min_uses=p['hmin'], point=pt)
    return dict(set='tuneb', shape=p['sh'], method=m, snr=p['snr'], seed=1010, batch=p['B'], min_vec=30, min_bit=0, min_uses=0, max_bits=20000 * p['bpu'], point=pt)


def job_h(pt, m):
    p = PT[pt]
    return dict(set='abl', shape=p['sh'], method=m, snr=p['snr'], seed=102, batch=p['B'], min_uses=p['hmin'], point=pt)


def rank(r, i):
    return (r['ber'], r['vec_err'] / r['uses'], i)


def edge_steps(c, grid):
    """Next cells beyond a grid edge, other settings held (section 5). grid: the cells known so far for this arm and S."""
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


plan, sel, log = [], dict(per_s={}, corner={}, pruned={}, budget={}, ap={}, pt={}), []


seen = set()


def add(j):
    k = (j['set'], j['shape'], j['method'], j['snr'])
    if k not in seen and done(*k) is None and not failed3(*k):
        seen.add(k)
        plan.append(j)


def survive(arm, S, c, st, pt):
    """Prune (section 5): None while unknown, else whether the cell runs. S = 64 is probed only if S = 32 survived, 128 only if 64 did."""
    p = PT[pt]
    if S >= 64:
        r = survive(arm, S // 2, c, st, pt)
        if r is not True:
            return r
    m = name(arm, S, c, st, p['Ns'])
    if done('probe', p['sh'], m, p['snr']) is None:
        add(job_probe(pt, m))
        return None
    x = x_of(counts('probe', p['sh'], m, p['snr']), p['sh'], S, 'F')
    return x is None or x <= XMAX


def finish_cells(arm, S, pt, base):
    """Stage A and corners for one (arm, S, point). Queues what can run. Returns the finished cells [(cell, start, method, result)]
    once complete, else None."""
    p = PT[pt]
    res, missing = [], False
    for c in base:
        for st in ('rand', 'bal'):
            m = name(arm, S, c, st, p['Ns'])
            if arm != 'ape' and pt in ('P1', 'P2') and S >= 32:
                r = survive(arm, S, c, st, pt)
                if r is None:
                    missing = True
                    continue
                if r is False:
                    sel['pruned'].setdefault('%s/%s/%d' % (pt, arm, S), []).append(m)
                    continue
            d = done('tunea', p['sh'], m, p['snr'])
            if d is None:
                add(job_a(pt, m)); missing = True
            else:
                res.append((c, st, m, d))
    if missing:
        return None
    if not res:                                                            # every cell pruned
        return []
    known = set(base)
    for rnd in range(2):                                                   # corners: at most two rounds
        c, st, m, d = res[min(range(len(res)), key=lambda i: rank(res[i][3], i))]
        nxt = [t for t in edge_steps(c, known) if t not in known]
        if not nxt:
            break
        wait = False
        for t in nxt:
            known.add(t)
            mt = name(arm, S, t, st, p['Ns'])
            dt = done('tunea', p['sh'], mt, p['snr'])
            if dt is None:
                add(job_a(pt, mt)); wait = True
            else:
                res.append((t, st, mt, dt))
        if wait:
            return None
    c, st, m, d = res[min(range(len(res)), key=lambda i: rank(res[i][3], i))]
    key = '%s/%s/%d' % (pt, arm, S)
    sel['per_s'][key] = dict(method=m, cell=list(c), start=st, ber=d['ber'], vec_err=d['vec_err'], uses=d['uses'])
    if edge_steps(c, known):                                               # reported, not extended further
        sel['corner'][key] = dict(method=m)
    return res


ready = {}
for pt in PT:
    for arm, Ss, cells in (('fam', SM, cells_m), ('far', SR, cells_r)):
        for S in Ss:
            ready[(pt, arm, S)] = finish_cells(arm, S, pt, cells(S))
    ready[(pt, 'ape', 0)] = finish_cells('ape', 0, pt, cells_a())
    p = PT[pt]
    rp = {}
    for bud in ('cyc', 'fl'):
        out, wait = [], False
        for a, b in cells_p():
            m = 'abl_ptb_%s_%g_%g_%d' % (bud, a, b, p['Ns'])
            d = done('tunea', p['sh'], m, p['snr'])
            if d is None:
                add(job_a(pt, m)); wait = True
            else:
                out.append((m, d))
        rp[bud] = None if wait else out
    ready[(pt, 'ptb', 0)] = rp

complete_a = all(v is not None for k, v in ready.items() if k[1] != 'ptb') and all(x is not None for k, v in ready.items() if k[1] == 'ptb' for x in v.values())
heldout_final = False
if complete_a:
    stage_b = True
    held = {}
    for pt, p in PT.items():
        pool = {'E': [], 'F-M': [], 'F-R': []}
        for S in SM:
            for c, st, m, d in ready[(pt, 'fam', S)]:
                cn = counts('tunea', p['sh'], m, p['snr'])
                for mod in ('E', 'F-M'):
                    pool[mod].append((x_of(cn, p['sh'], S, 'E' if mod == 'E' else 'F'), d, m))
        for S in SR:
            for c, st, m, d in ready[(pt, 'far', S)]:
                pool['F-R'].append((x_of(counts('tunea', p['sh'], m, p['snr']), p['sh'], S, 'F'), d, m))
        groups = {}
        for mod, L in pool.items():
            for B in BUDGETS:
                el = sorted([t for t in L if t[0] is not None and t[0] <= B], key=lambda t: (t[1]['ber'], t[1]['vec_err'] / t[1]['uses'], t[2]))
                groups['%s/%s/%g' % (pt, mod, B)] = [t[2] for t in el[:3]]
        ra = ready[(pt, 'ape', 0)]
        groups['%s/ape' % pt] = [t[2] for t in sorted(ra, key=lambda t: (t[3]['ber'], t[3]['vec_err'] / t[3]['uses'], t[2]))[:3]]
        for bud in ('cyc', 'fl'):
            groups['%s/ptb/%s' % (pt, bud)] = [t[0] for t in sorted(ready[(pt, 'ptb', 0)][bud], key=lambda t: (t[1]['ber'], t[1]['vec_err'] / t[1]['uses'], t[0]))[:3]]
        for g, ms in groups.items():
            rs = []
            for m in ms:
                d = done('tuneb', p['sh'], m, p['snr'])
                if d is None:
                    add(job_b(pt, m)); stage_b = False
                else:
                    rs.append((d['ber'], d['vec_err'] / d['uses'], m))
            if ms and len(rs) == len(ms):
                best = min(rs)[2]
                sel['budget' if g.count('/') == 2 and '/ptb/' not in g else ('pt' if '/ptb/' in g else 'ap')][g] = dict(method=best, stage_b=rs)
    if stage_b:
        heldout_final = True
        for pt, p in PT.items():
            L = [v['method'] for k, v in sel['per_s'].items() if k.startswith(pt + '/') and '/ape/' not in k]
            L += [v['method'] for k, v in sel['budget'].items() if k.startswith(pt + '/')]
            L += [v['method'] for k, v in sel['ap'].items() if k.startswith(pt + '/')]
            L += [v['method'] for k, v in sel['pt'].items() if k.startswith(pt + '/')]
            L.append('abl_ape_0.3_0.3_0.4_bal_%d' % p['Ns'])
            held[pt] = sorted(set(L))
            for m in held[pt]:
                add(job_h(pt, m))
        sel['held'] = held
sel['complete_a'], sel['heldout_final'] = complete_a, heldout_final


def cost(j):
    mult = {'probe': 0, 'tunea': 1, 'tuneb': 2, 'abl': 3}[j['set']]
    a = j['method'].split('_')
    S = int(a[2]) if a[1] in ('fam', 'far') else 128 if a[1] == 'ape' else 8
    return (mult, {'P3': 0, 'P1': 1, 'P2': 2}[j['point']], S, j['method'])


plan.sort(key=cost)
out = dict(host='hostB', amendment='A5.5 exploratory', tuned_file=os.path.join(os.path.dirname(os.path.abspath(ROOT)), 'tuned_a52.json'), jobs=plan)
with open(os.path.join(ROOT, 'plan.json.tmp'), 'w') as f:
    json.dump(out, f, indent=0)
os.replace(os.path.join(ROOT, 'plan.json.tmp'), os.path.join(ROOT, 'plan.json'))
with open(os.path.join(ROOT, 'select.json.tmp'), 'w') as f:
    json.dump(sel, f, indent=1)
os.replace(os.path.join(ROOT, 'select.json.tmp'), os.path.join(ROOT, 'select.json'))
start = 0
for j in plan:
    cl = os.path.join(jdir(j['set'], j['shape'], j['method'], j['snr']), 'claim.json')
    if not os.path.exists(cl):
        start += 1
    else:
        try:
            start += not os.path.exists('/proc/%d' % int(json.load(open(cl))['pid']))
        except Exception:
            pass
fin = complete_a and heldout_final and not plan
print(len(plan), start, int(fin))
