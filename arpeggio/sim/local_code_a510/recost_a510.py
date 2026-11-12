#!/usr/bin/env python3
"""A5.10 re-costing (PROTOCOL_A510.md section 6). Read-only on the A5.5 results. Copies of A5.5's ref_cost, jdir, done and counts
(src/a55_plan.py, sha c099cf3f), not an import (importing a55_plan would rewrite plan.json).
1. Reproduction check: under model F (tests + F) the F-R budget groups of select.json must be reproduced exactly.
2. Model F' = S P + F per anneal; for B in (0.5, 1): top three stage-A cells -> stage B (existing tuneb runs) -> pick, by A5.5's order.
Usage: recost_a510.py A55_ROOT TUNED_JSON OUT.json"""
import glob, json, os, sys
import numpy as np

ROOT, TUNED, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PT = {'P1': dict(sh='x16', snr=20.0), 'P2': dict(sh='x32', snr=22.0), 'P3': dict(sh='q32', snr=14.0)}
PHI = json.load(open(TUNED))['flip_phi']
BUDGETS = (0.5, 1, 2, 3)


def ref_cost(sh, K):
    L = 128 * 2 * K
    return L + PHI[sh][str(K)] * L


def jdir(st, sh, m, snr):
    return os.path.join(ROOT, st, sh, m, 'snr_%05.2f' % snr)


def done(st, sh, m, snr):
    p = os.path.join(jdir(st, sh, m, snr), 'done.json')
    return json.load(open(p)) if os.path.exists(p) else None


def counts(st, sh, m, snr):
    tot = {}
    for f in sorted(glob.glob(os.path.join(jdir(st, sh, m, snr), 'b*.npz'))):
        z = np.load(f, allow_pickle=False)
        for K, v in json.loads(str(z['info'])).get('count', {}).items():
            d = tot.setdefault(K, dict(flips=0.0, tests=0, anneals=0, N=v['N']))
            d['flips'] += v['flips']; d['tests'] += v.get('tests', 0); d['anneals'] += v['anneals']
    return {K: dict(F=v['flips'] / v['anneals'], tests=v['tests'] / v['anneals'], N=v['N']) for K, v in tot.items() if v['anneals']}


def x_model(cnt, sh, S, model):
    xs = []
    for K, v in cnt.items():
        c = v['tests'] + v['F'] if model == 'F' else S * 2 * int(K) + v['F']          # F: A5.5's model; F': S P + F
        xs.append(c / ref_cost(sh, int(K)))
    return float(np.mean(xs)) if xs else None


def order(t):          # A5.5 section 5: BER, then rate of erroneous uses, then name
    return (t['d']['ber'], t['d']['vec_err'] / t['d']['uses'], t['m'])


sel = json.load(open(os.path.join(ROOT, 'select.json')))
ana = json.load(open(os.path.join(ROOT, 'analysis.json')))
flips = json.load(open(os.path.join(ROOT, 'flips.json')))
res = dict(note='A5.10 section 6; read-only on ' + ROOT, repro={}, recost={})
repro_ok = True
for pt, p in PT.items():
    pool = []
    for d_ in sorted(glob.glob(os.path.join(ROOT, 'tunea', p['sh'], 'abl_far_*'))):
        m = os.path.basename(d_)
        d = done('tunea', p['sh'], m, p['snr'])
        if d is None:
            continue
        S = int(m.split('_')[2])
        cn = counts('tunea', p['sh'], m, p['snr'])
        pool.append(dict(m=m, S=S, d=d, cnt=cn, xF=x_model(cn, p['sh'], S, 'F'), xFp=x_model(cn, p['sh'], S, 'Fp')))
    for B in BUDGETS:
        mine = [t['m'] for t in sorted([t for t in pool if t['xF'] is not None and t['xF'] <= B], key=order)[:3]]
        g = sel['budget'].get('%s/F-R/%g' % (pt, B))
        theirs = [x[2] for x in g['stage_b']] if g else []
        ok = mine == theirs
        repro_ok &= ok
        res['repro']['%s/%g' % (pt, B)] = dict(ok=ok, mine=mine, select=theirs)
    if not repro_ok:
        continue
    for B in (0.5, 1):
        grp = sorted([t for t in pool if t['xFp'] is not None and t['xFp'] <= B], key=order)[:3]
        rs, need_b = [], []
        for t in grp:
            db = done('tuneb', p['sh'], t['m'], p['snr'])
            if db is None:
                need_b.append(t['m'])
            else:
                rs.append((db['ber'], db['vec_err'] / db['uses'], t['m']))
        e = dict(group=[dict(method=t['m'], S=t['S'], x_Fp_stage_a=t['xFp'], x_F_stage_a=t['xF'], ber_a=t['d']['ber']) for t in grp],
                 stage_b=rs, need_stage_b=need_b)
        if grp and not need_b:
            pick = min(rs)[2]
            e['pick'] = pick
            if pick in flips:
                xs = [(t_S * 2 * int(K) + v['F']) / ref_cost(p['sh'], int(K)) for t_S in [int(pick.split('_')[2])] for K, v in flips[pick].items()]
                e['x_Fp_held'] = float(np.mean(xs)); e['x_Fp_source'] = 'flips.json (A5.5 section 7)'
            else:
                e['x_Fp_held'] = [t for t in grp if t['m'] == pick][0]['xFp']; e['x_Fp_source'] = 'stage-A counters (seed 1000)'
            h = ana['points'].get(pt, {}).get('picks', {}).get(pick)
            e['held_out'] = h
            e['needs_held_out'] = h is None
        res['recost']['%s/%g' % (pt, B)] = e
res['repro_ok'] = repro_ok
json.dump(res, open(OUT, 'w'), indent=1)
print('reproduction check:', 'PASS' if repro_ok else 'FAIL')
for k, v in res['repro'].items():
    if not v['ok']:
        print('  repro mismatch', k, v)
for k, e in res['recost'].items():
    print(k, 'group', [(g['method'], round(g['x_Fp_stage_a'], 3), g['ber_a']) for g in e['group']], 'need stage B', e['need_stage_b'],
          'pick', e.get('pick'), 'x_Fp_held', None if e.get('x_Fp_held') is None else round(e['x_Fp_held'], 3),
          'held-out', None if not e.get('held_out') else {k2: e['held_out'].get(k2) for k2 in ('ratio', 'lo', 'hi', 'term', 'uses')})
