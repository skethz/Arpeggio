#!/usr/bin/env python3
"""Amendment A2 (STATUS.md, 24 Oct 09:40 CEST): hostA GPU7 withdrawn for ~2.5 days. Builds plan_hostb_v2.json =
the frozen hostB plan (minus its AHC-kernel ambiguity jobs) + every hostA job, migrated: K-best / sphere decoder to
hostB's CPU worker; 16x16 16-QAM MDI-AHC kernel jobs (mdiahck*) -> PyTorch mimo.ahc (mdiahc*), identical start-state
draws; ambiguity tests on PyTorch AHC (ambt_*, reference mdiahc64). The B200-side E2 job that had not finished is listed
in STATUS.md as waiting for B200. Usage: make_plan_v2.py PLAN_DIR"""
import json, os, sys
D = sys.argv[1]
mo = json.load(open(os.path.join(D, 'plan_hostb.json')))
zi = json.load(open(os.path.join(D, 'plan_hosta.json')))
jobs = [j for j in mo['jobs'] if j['set'] != 'amb']
seen = set((j['set'], j['shape'], j['method'], j['snr']) for j in jobs)
for j in zi['jobs']:
    if j['set'] == 'equiv':
        continue
    j = dict(j)
    if j['set'] == 'amb':
        continue
    if j['shape'] == 'x16' and j['method'].startswith('mdiahck'):
        j['method'] = 'mdiahc' + j['method'][7:]
    k = (j['set'], j['shape'], j['method'], j['snr'])
    if k not in seen:
        jobs.append(j); seen.add(k)
for sh, snr, ms in (('x16', 20.0, ['mdiahc64', 'ambt_om2_64', 'ambt_x0sd_64', 'ambt_floor_64', 'sic', 'sicc']),
                    ('x16', 24.0, ['sic', 'sicc']), ('q32', 13.0, ['mdiahc64', 'ambt_x0sd_64'])):
    for m in ms:
        jobs.append(dict(set='amb', shape=sh, method=m, snr=snr, seed=105, batch={'x16': 2000, 'q32': 4000}[sh],
                         min_uses=16000, pri=3.5))
jobs.sort(key=lambda j: (j['pri'], j['set'], j['shape'], j['method'], j['snr']))
plan = dict(host='hostB', amendment='A2', tuned_file=mo['tuned_file'], jobs=jobs)
json.dump(plan, open(os.path.join(D, 'plan_hostb_v2.json'), 'w'), indent=0)
import collections
print(len(jobs), dict(collections.Counter(j['set'] for j in jobs)), sum(j['method'].startswith(('kbest', 'sd')) for j in jobs), 'cpu jobs')
