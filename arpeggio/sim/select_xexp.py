#!/usr/bin/env python3
"""A3 exploratory stage 2: per point (P2, P3) and family (sym = variant (x); ane = Antiphase alternation, (q, T)),
pick the tuning-seed setting with the fewest bit errors (then fewest erroneous uses, then plan order) and write
plan_hostb_xexp_v2.json = stage-1 jobs + held-out seed-102 jobs ('xheld') for the picks (stopping rule of PROTOCOL 3.4,
minimum 4,000 (P2) / 8,000 (P3) uses). Refuses to overwrite. Usage: select_xexp.py ROOT PLAN_IN PLAN_OUT"""
import json, os, sys
root, pin, pout = sys.argv[1:4]
if os.path.exists(pout):
    sys.exit('refusing: exists')
plan = json.load(open(pin))
pick = {}
for i, j in enumerate(plan['jobs']):
    d = os.path.join(root, 'xtune', j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json')
    if not os.path.exists(d):
        sys.exit('not finished: ' + j['method'] + ' ' + j['shape'])
    r = json.load(open(d))
    fam = 'sym' if j['method'].startswith('abl_symt') else 'ane'
    key = (r['bit_err'], r['vec_err'], i)
    k = (j['point'], fam)
    if k not in pick or key < pick[k][0]:
        pick[k] = (key, j)
jobs = list(plan['jobs'])
sel = {}
for (pt, fam), (key, j) in sorted(pick.items()):
    sel['%s_%s' % (pt, fam)] = dict(method=j['method'], bit_err=key[0], vec_err=key[1])
    jobs.append(dict(set='xheld', shape=j['shape'], method=j['method'], snr=j['snr'], seed=102, batch=j['batch'],
                     min_uses=4000 if pt == 'P2' else 8000, point=pt, pri=1))
# A4 (exploratory): extend Antiphase's Table II grid (seed 101, same draws) to the upper end of MDI-AHC's grid, so that
# the high-SNR floors of both detectors are compared on the same uses (R3 M5; chair 4.8)
for sh, m, snrs, b in (('x16', 'mdiane64', (24.0, 24.5, 25.0, 25.5, 26.0), 2000), ('x32', 'mdiane128', (22.0, 22.5, 23.0, 23.5, 24.0), 1000)):
    for snr in snrs:
        jobs.append(dict(set='tab2', shape=sh, method=m, snr=snr, seed=101, batch=b, pri=2, amendment='A4'))
json.dump(dict(host='hostB', amendment='A3 exploratory, stage 2 + A4 grid extension', selection=sel, jobs=jobs), open(pout, 'w'), indent=0)
print(json.dumps(sel, indent=1))
