#!/usr/bin/env python3
"""PROTOCOL.md 4.3: picks each tuned variant's setting on the tuning seed (1000, P1, 4000 uses): lowest bit-error count;
ties -> fewer erroneous uses -> first in plan order. Writes results/tuned.json (never overwritten: refuses if present)."""
import json, os, sys
root, plan, out = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.exists(out):
    sys.exit('refusing: %s exists' % out)
jobs = [j for j in json.load(open(plan))['jobs'] if j['set'] == 'tune']
fam = {'qdim': 'abl_qdimc_', 'sa': 'abl_sat_', 'sym': 'abl_symt_prop_', 'symw': 'abl_symt_win_'}
res, table = {}, []
for name, pre in fam.items():
    best = None
    for i, j in enumerate(jobs):
        if not j['method'].startswith(pre):
            continue
        d = os.path.join(root, 'tune', j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json')
        if not os.path.exists(d):
            sys.exit('not finished: ' + j['method'])
        r = json.load(open(d))
        table.append(dict(family=name, method=j['method'], bit_err=r['bit_err'], vec_err=r['vec_err'], uses=r['uses']))
        key = (r['bit_err'], r['vec_err'], i)
        if best is None or key < best[0]:
            best = (key, j['method'])
    v = best[1][len(pre):].rsplit('_', 1)[0].split('_')
    if name == 'qdim':
        res[name] = dict(c=float(v[0]), q0=float(v[1]), T=float(v[2]))
    elif name == 'sa':
        res[name] = dict(T0=float(v[0]), T1=float(v[1]))
    else:
        res[name] = dict(T=float(v[0]), q=float(v[1]))
    res[name]['from'] = best[1]
json.dump(res, open(out, 'w'), indent=1)
json.dump(table, open(out.replace('.json', '_table.json'), 'w'), indent=1)
print(json.dumps(res, indent=1))
