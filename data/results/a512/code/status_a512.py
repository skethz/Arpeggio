#!/usr/bin/env python3
"""A5.12: prints 'left N failed_max F' (jobs without done.json; most failed attempts of any job). Usage: status_a512.py PLAN ROOT"""
import glob, json, os, sys
plan, root = json.load(open(sys.argv[1])), sys.argv[2]
left, fmax = 0, 0
for j in plan['jobs']:
    d = os.path.join(root, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    if not os.path.exists(os.path.join(d, 'done.json')):
        left += 1
    fmax = max(fmax, len(glob.glob(os.path.join(d, 'failed.*.json'))))
print('left', left, 'failed_max', fmax)
