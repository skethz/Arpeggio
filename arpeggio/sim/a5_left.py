#!/usr/bin/env python3
"""Prints 'tier1_left N p2col_left M tier2_left K' for plan_hostb_a5.json (jobs without done.json)."""
import json, os
R = '<SCRATCH>/ap_ber_20261024/results'
p = json.load(open(R + '/plan_hostb_a5.json'))
t1 = p2 = t2 = 0
for j in p['jobs']:
    if os.path.exists(os.path.join(R, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json')):
        continue
    if j.get('tier', 1) == 2:
        t2 += 1
    else:
        t1 += 1
    if j['set'] == 'abl' and j['shape'] == 'x32' and any(j['method'].startswith(x) for x in ('abl_colk', 'abl_dimk', 'abl_symdk')):
        p2 += 1
print('tier1_left', t1, 'p2col_left', p2, 'tier2_left', t2)
