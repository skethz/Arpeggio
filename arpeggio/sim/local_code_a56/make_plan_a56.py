#!/usr/bin/env python3
"""A5.6 plan and selection (PROTOCOL_A56.md sections 5-7). Pure function of the saved results: writes ROOT/plan.json with every job that can run
now, in priority order, and ROOT/select.json with the picks so far. Re-run by the supervisor; safe to repeat. Usage: make_plan_a56.py ROOT"""
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

ROOT = sys.argv[1]
RES = os.path.dirname(os.path.abspath(ROOT))
TUNE, HELD = 1020, 102
PT = {'P1': dict(sh='x16', snr=20.0, Ns=32, B=2000, bpu=64, Rmax=3, hmin=8000, tcap=64000, gcap=8000, bigcap=40000),
      'P2': dict(sh='x32', snr=22.0, Ns=8, B=1000, bpu=128, Rmax=3, hmin=4000, tcap=32000, gcap=4000, bigcap=20000),
      'P3': dict(sh='q32', snr=14.0, Ns=8, B=4000, bpu=64, Rmax=1, hmin=8000, tcap=15_625_000),
      'P4': dict(sh='x16', snr=31.02, Ns=8, B=2000, bpu=64, Rmax=3, hmin=8000, tcap=156_250)}
SPLIT = {'P1': {1: [(16, 256), (32, 128), (64, 64), (256, 16), (512, 8)], 0.5: [(128, 16), (64, 32), (32, 64), (16, 128)],
                2: [(128, 64), (64, 128), (32, 256), (256, 32), (512, 16)]},
         'P2': {1: [(16, 64), (32, 32), (64, 16), (256, 4), (512, 2)], 0.5: [(128, 4), (64, 8), (32, 16), (16, 32)],
                2: [(128, 16), (64, 32), (32, 64), (256, 8), (512, 4)]}}
REINVEST = {'P1': (128, 256, 384), 'P2': (32, 64, 128)}                         # with (128, 2 Ns) from SPLIT, Ns grows by 2, 4, 8
LENGTHS = (32, 64, 256, 512, 1024)
TGRID = (0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 2.4)
KAPPAS = (0.15, 0.3, 0.6)
SA_SPLIT = {2: 64, 4: 32, 8: 16, 16: 8}


def M(pt, Sk=128, T0=0.3, T1=0.3, q=0.4, ka=0.0, sched='alt', Ns=None):
    return 'a56_%d_%g_%g_%g_%g_%s_%d' % (Sk, T0, T1, q, ka, sched, PT[pt]['Ns'] if Ns is None else Ns)


def jdir(st, sh, m, snr):
    return os.path.join(ROOT, st, sh, m, 'snr_%05.2f' % snr)


def done(j):
    p = os.path.join(jdir(j['set'], j['shape'], j['method'], j['snr']), 'done.json')
    return json.load(open(p)) if os.path.exists(p) else None


def failed3(j):
    return len(glob.glob(os.path.join(jdir(j['set'], j['shape'], j['method'], j['snr']), 'failed.*.json'))) >= 3


plan, seen = [], set()


def add(j):
    k = (j['set'], j['shape'], j['method'], j['snr'])
    if k in seen:
        return
    seen.add(k)
    if done(j) is None and not failed3(j):
        plan.append(j)


def tune(pt, m, st):
    p = PT[pt]
    return dict(set=st, shape=p['sh'], method=m, snr=p['snr'], seed=TUNE, batch=p['B'], point=pt, min_uses=p['hmin'], max_bits=p['tcap'] * p['bpu'])


def grid(pt, m):
    p = PT[pt]
    return dict(set='G', shape=p['sh'], method=m, snr=p['snr'], seed=TUNE, batch=p['B'], point=pt, min_vec=30, min_bit=0, min_uses=0, max_bits=p['gcap'] * p['bpu'])


def held(pt, m, st='H', stream=None, cap=None, **kw):
    p = PT[pt]
    j = dict(set=st, shape=p['sh'], method=m, snr=p['snr'], seed=HELD, batch=p['B'], point=pt, min_uses=p['hmin'], **kw)
    if pt == 'P3':
        j['max_bits'] = p['tcap'] * p['bpu']
    if cap:
        j['max_bits'] = cap * p['bpu']
    if stream:
        j['stream'] = stream
    return j


def replay(pt, m, stream, sub, st='R', seed=HELD, nb=None):
    p = PT[pt]
    d = os.path.join(RES, sub)
    n = nb if nb is not None else len(glob.glob(os.path.join(d, 'b*.npz')))
    return dict(set=st, shape=p['sh'], method=m, stream=stream, snr=p['snr'], seed=seed, batch=p['B'], point=pt, saved=d, n_batches=n)


def base_tune(pt):
    p = PT[pt]
    if pt in ('P1', 'P2'):
        return dict(set='A', shape=p['sh'], method=M(pt), snr=p['snr'], seed=TUNE, batch=p['B'], point=pt, min_uses=40000)
    return dict(set='A', shape=p['sh'], method=M(pt), snr=p['snr'], seed=TUNE, batch=p['B'], point=pt, max_bits=p['tcap'] * p['bpu'])


def best(jobs):
    """Lowest BER among finished jobs, ties by erroneous uses, then listed order. None until all are finished or failed three times."""
    rs = []
    for i, j in enumerate(jobs):
        d = done(j)
        if d is None:
            if failed3(j):
                continue
            return None
        rs.append((d['ber'], d['vec_err'] / max(d['uses'], 1), i, j, d))
    if not rs:
        return None
    return min(rs, key=lambda r: r[:3])


def ratio(j, ref):
    """Paired BER ratio of j to ref on the tuning seed; None if either is missing."""
    a = AN.load(jdir(j['set'], j['shape'], j['method'], j['snr']))
    b = AN.load(jdir(ref['set'], ref['shape'], ref['method'], ref['snr']))
    if a is None or b is None:
        return None
    n = min(len(a['biterr']), len(b['biterr']))
    x, y = int(a['biterr'][:n].astype(np.int64).sum()), int(b['biterr'][:n].astype(np.int64).sum())
    return x / y if y else None


sel = dict(F={}, D={}, C={}, B={}, N={}, G={}, J={}, c={}, sa_split={}, promoted=[])
# ---------------- priority order: replays and the tuning baselines, then the review's items, then the search over schedules
add(replay('P1', M('P1'), 'mdiane32', 'abl/x16/mdiane32/snr_20.00'))
add(replay('P3', M('P3'), 'mdiane8', 'abl/q32/mdiane8/snr_14.00'))
for pt in ('P1', 'P3', 'P4', 'P2'):
    add(base_tune(pt))
add(replay('P2', M('P2'), 'mdiane8', 'abl/x32/mdiane8/snr_22.00'))
add(held('P3', M('P3'), 'R3', stream='mdiane8'))
add(held('P4', M('P4'), 'R', stream='mdiane8', max_bits=PT['P4']['tcap'] * PT['P4']['bpu']))
for pt in ('P3', 'P1', 'P2'):                                              # X4
    add(held(pt, M(pt, sched='lane'), 'L'))
Fj = {pt: [tune(pt, M(pt, T0=T, T1=T, q=0.0), 'F') for T in TGRID] for pt in ('P3', 'P1', 'P2')}   # X5a
for pt in Fj:
    for j in Fj[pt]:
        add(j)
TX = {pt: list(TGRID) for pt in Fj}                                        # amendment 2: if the lowest T wins, add T/2, at most twice
for pt in Fj:
    for _ in range(2):
        r = best(Fj[pt])
        if r is None or float(r[3]['method'].split('_')[2]) != min(TX[pt]):
            break
        Tn = min(TX[pt]) / 2
        TX[pt].append(Tn)
        j = tune(pt, M(pt, T0=Tn, T1=Tn, q=0.0), 'F')
        Fj[pt].append(j)
        add(j)
Dj = {pt: [tune(pt, M(pt, ka=k), 'D') for k in KAPPAS] for pt in ('P1', 'P2')}
Cj = {pt: [dict(tune(pt, M(pt), 'C%d' % R), Rmax=R) for R in (1, 2)] for pt in ('P1', 'P2')}
for pt in ('P1', 'P2'):
    for j in Dj[pt] + Cj[pt]:
        add(j)
add(replay('P1', 'abl_sa_32', 'abl_sa_32', 'abl/x16/abl_sa_32/snr_20.00', 'S'))
add(replay('P1', 'mdiahc32', 'mdiahc32', 'abl/x16/mdiahc32/snr_20.00', 'S'))
add(replay('P2', 'mdiahc8', 'mdiahc8', 'abl/x32/mdiahc8/snr_22.00', 'S'))
add(replay('P1', M('P1', Ns=64), 'mdiane64', 'tab2/x16/mdiane64/snr_20.00', 'PC', seed=101))
Bj = {pt: {b: [tune(pt, M(pt, Sk=s, Ns=n), 'B') for s, n in v] for b, v in SPLIT[pt].items()} for pt in SPLIT}
for pt in Bj:
    for b in (1, 2, 0.5):
        for j in Bj[pt][b]:
            add(j)
Nj = {pt: [tune(pt, M(pt, Ns=n), 'N') for n in REINVEST[pt]] for pt in REINVEST}

# ---------------- selection on the tuning seed; picks go to the held-out seed ahead of the length grid
pick = []
for pt, js in Fj.items():                                                  # the q = 0 answer is wanted in every outcome
    r = best(js)
    if r:
        sel['F'][pt] = dict(method=r[3]['method'], ber=r[4]['ber'], vec_err=r[4]['vec_err'], uses=r[4]['uses'])
        pick.append(held(pt, r[3]['method'], 'HF'))
for fam, Jd in (('D', Dj), ('C', Cj)):
    for pt, js in Jd.items():
        r = best(js)
        if r:
            q = ratio(r[3], base_tune(pt))
            sel[fam][pt] = dict(method=r[3]['method'], set=r[3]['set'], ber=r[4]['ber'], ratio_to_i=q, promoted=bool(q is not None and q <= 0.9))
            if q is not None and q <= 0.9:
                j = held(pt, r[3]['method'], 'H' + r[3]['set'])
                if 'Rmax' in r[3]:
                    j['Rmax'] = r[3]['Rmax']
                pick.append(j)
for pt, bys in Bj.items():
    for b, js in bys.items():
        r = best(js)
        if not r:
            continue
        n128 = PT[pt]['Ns'] * b
        ref = base_tune(pt) if b == 1 else tune(pt, M(pt, Ns=int(n128)), 'B')
        q = ratio(r[3], ref)
        ok = bool(q is not None and q <= 0.9 and AN.sk_of(r[3]['method']) != 128)
        sel['B']['%s/%g' % (pt, b)] = dict(method=r[3]['method'], ber=r[4]['ber'], vec_err=r[4]['vec_err'], ratio_to_128=q, promoted=ok)
        if ok:
            pick.append(held(pt, r[3]['method'], 'HB'))
            if b != 1:
                pick.append(held(pt, M(pt, Ns=int(n128)), 'HB'))

# early stop threshold (tuning seed) and reinvestment
for pt in PT:
    j = base_tune(pt)
    if done(j) is None:
        continue
    run = AN.load(jdir(j['set'], j['shape'], j['method'], j['snr']))
    cyc = AN.cyc_table(run, PT[pt]['Rmax'])
    c = AN.pick_c(run, cyc)
    sel['c'][pt] = dict(c=c, cyc_per_anneal=cyc.tolist(), uses=len(run['biterr']), vec_err=j and done(j)['vec_err'])
    if pt not in REINVEST or c is None:
        continue
    cand = [tune(pt, M(pt, Ns=PT[pt]['Ns'] * 2), 'B')] + Nj[pt]
    if not all(done(x) is not None or failed3(x) for x in cand):
        continue
    budget = float(AN.nostop_cycles(run, cyc).mean())
    rows = []
    for x in cand:
        if done(x) is None:
            continue
        r2 = AN.load(jdir(x['set'], x['shape'], x['method'], x['snr']))
        cy2 = AN.cyc_table(r2, PT[pt]['Rmax'])
        be, C, _ = AN.stop(r2, c, cy2)
        rows.append(dict(method=x['method'], ber=float(be.sum()) / (len(be) * PT[pt]['bpu']), err=int((be > 0).sum()), uses=len(be), cyc=float(C.mean()), x=float(C.mean()) / budget))
    feas = [r for r in rows if r['x'] <= 1.0]
    sel['N'][pt] = dict(budget=budget, rows=rows)
    if feas:
        w = min(feas, key=lambda r: (r['ber'], r['cyc']))
        sel['N'][pt]['pick'] = w
        pick.append(held(pt, w['method'], 'HN', cap=PT[pt]['bigcap']))

# SA split of the review's X2, with the cells A5.5 picked at Ns of the point
sp = os.path.join(RES, 'a55', 'select.json')
if os.path.exists(sp):
    per = json.load(open(sp)).get('per_s', {})
    for S, Ns in SA_SPLIT.items():
        v = per.get('P1/fam/%d' % S)
        if v:
            T0, T1 = v['cell'][0], v['cell'][1]
            m = 'abl_fam_%d_%g_%g_%s_%d' % (S, T0, T1, v['start'], Ns)
            sel['sa_split'][str(S)] = m
            pick.append(held('P1', m, 'HS'))
    # amendment 4: SA with the same stop and more anneals; same draws and length as Antiphase's HN arm, cell as A5.5 picked it (final once per_s has the key)
    for pt, (S, Ns, nb) in {'P1': (4, 384, 17), 'P2': (2, 128, 20)}.items():
        v = per.get('%s/fam/%d' % (pt, S))
        if v:
            p = PT[pt]
            add(dict(set='HR', shape=p['sh'], method='abl_fam_%d_%g_%g_%s_%d' % (S, v['cell'][0], v['cell'][1], v['start'], Ns), snr=p['snr'], seed=HELD, batch=p['B'], point=pt, n_batches=nb))
for j in pick:
    add(j)
# amendment 3: the lowest-BER budget-1 split within 15% of the budget's measured cycles also goes to the held-out seed; then (Sk, Ns) and kappa together at P1
late = []
for pt in Bj:
    js = Bj[pt][1]
    a0 = AN.load(jdir('A', PT[pt]['sh'], M(pt), PT[pt]['snr']))
    if a0 is None or done(base_tune(pt)) is None or best(js) is None:
        continue
    bud = float(AN.nostop_cycles(a0, AN.cyc_table(a0, PT[pt]['Rmax'])).mean())
    rows = []
    for j in js:
        if done(j) is None:
            continue
        r2 = AN.load(jdir(j['set'], j['shape'], j['method'], j['snr']))
        x = float(AN.nostop_cycles(r2, AN.cyc_table(r2, PT[pt]['Rmax'])).mean()) / bud
        if abs(x - 1) <= 0.15:
            rows.append((done(j)['ber'], j['method'], x, j))
    if rows:
        w = min(rows, key=lambda t: t[:2])
        q = ratio(w[3], base_tune(pt))
        sel['B'][pt + '/1/within15'] = dict(method=w[1], ber=w[0], x_cycles=w[2], ratio_to_128=q, promoted=bool(q is not None and q <= 0.9))
        if q is not None and q <= 0.9:
            late.append(held(pt, w[1], 'HB'))
JOINT = {'P1': [(64, 64, 0.15), (64, 64, 0.3), (32, 128, 0.15), (32, 128, 0.3)]}
for pt, v in JOINT.items():
    js = [tune(pt, M(pt, Sk=s0, Ns=n0, ka=k0), 'J') for s0, n0, k0 in v]
    late += js
    r = best(js)
    if r:
        a56 = r[3]['method'].split('_')
        cmp0 = tune(pt, M(pt, Sk=int(a56[1]), Ns=int(a56[7])), 'B')
        q = ratio(r[3], cmp0)
        sel['J'][pt] = dict(method=r[3]['method'], ber=r[4]['ber'], ratio_to_split=q, promoted=bool(q is not None and q <= 0.9))
        if q is not None and q <= 0.9:
            late += [held(pt, r[3]['method'], 'HJ'), held(pt, cmp0['method'], 'HB')]
for j in late:
    add(j)
sel['promoted'] = [[j['set'], j['point'], j['method']] for j in pick + late if j['set'] != 'J']

# X3's float arm continues the saved series on the same draws
add(dict(set='X3F', shape='x16', method=M('P1'), stream='mdiane32', snr=20.0, seed=HELD, batch=2000, point='P1', first_batch=10, min_vec=1900, min_bit=0, min_uses=0, max_bits=380000 * 64))
add(dict(set='X3F', shape='x32', method=M('P2'), stream='mdiane8', snr=22.0, seed=HELD, batch=1000, point='P2', first_batch=43, min_vec=1900, min_bit=0, min_uses=0, max_bits=257000 * 128))
for pt in Nj:
    for j in Nj[pt]:
        add(j)
add(replay('P2', M('P2', Ns=128), 'mdiane128', 'tab2/x32/mdiane128/snr_22.00', 'PC', seed=101, nb=20))
# length grid (lowest priority); per length and point the best cell goes to the held-out seed, paired with A5.4's frozen schedule at that length
Gj = {}
for pt in ('P1', 'P2'):
    for Sk in LENGTHS:
        cells = [(T, T, q) for q in (0.2, 0.4) for T in (0.1, 0.2, 0.3, 0.5)] + [(a, 0.2, q) for a in (0.6, 1.2) for q in (0.2, 0.4)]
        Gj[(pt, Sk)] = [grid(pt, M(pt, Sk=Sk, T0=a, T1=b, q=q)) for a, b, q in cells]
for Sk in (64, 32, 256, 512, 1024):
    for pt in ('P1', 'P2'):
        for j in Gj[(pt, Sk)]:
            add(j)
for (pt, Sk), js in Gj.items():
    r = best(js)
    if r:
        sel['G']['%s/%d' % (pt, Sk)] = dict(method=r[3]['method'], ber=r[4]['ber'], vec_err=r[4]['vec_err'], uses=r[4]['uses'])
        add(held(pt, r[3]['method'], 'HG', cap=PT[pt]['bigcap'] if Sk >= 512 else None))
plan.sort(key=lambda j: j['set'] != 'HR')                                  # stable: these go first, the rest keep their order
tmp = os.path.join(ROOT, '.plan.tmp')
json.dump(dict(jobs=plan), open(tmp, 'w'))
os.rename(tmp, os.path.join(ROOT, 'plan.json'))
tmp = os.path.join(ROOT, '.select.tmp')
json.dump(sel, open(tmp, 'w'), indent=1)
os.rename(tmp, os.path.join(ROOT, 'select.json'))
print(len(plan))
