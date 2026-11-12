#!/usr/bin/env python3
"""A5.6 status. Usage: a56_status.py ROOT [--brief]. --brief prints: jobs in plan, jobs in plan that can start, finished, failed three times."""
import glob
import json
import os
import sys

ROOT = sys.argv[1]
plan = json.load(open(os.path.join(ROOT, 'plan.json')))['jobs'] if os.path.exists(os.path.join(ROOT, 'plan.json')) else []
done = glob.glob(os.path.join(ROOT, '*', '*', '*', 'snr_*', 'done.json'))
fails = {}
for f in glob.glob(os.path.join(ROOT, '*', '*', '*', 'snr_*', 'failed.*.json')):
    fails.setdefault(os.path.dirname(f), []).append(f)
start = 0
for j in plan:
    d = os.path.join(ROOT, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    if not os.path.exists(os.path.join(d, 'claim.json')):
        start += 1
if '--brief' in sys.argv:
    print(len(plan), start, len(done), sum(len(v) >= 3 for v in fails.values()))
    sys.exit()
secs = 0.0
by = {}
for f in done:
    p = f.split(os.sep)
    s = p[-5]
    r = json.load(open(f))
    x = by.setdefault(s, [0, 0, 0])
    x[0] += 1; x[1] += r['uses']; x[2] += r['vec_err']
print('set   finished  uses  err_uses')
for s in sorted(by):
    print('%-5s %5d %10d %7d' % (s, *by[s]))
act = glob.glob(os.path.join(ROOT, '*', '*', '*', 'snr_*', 'claim.json'))
now = []
for c in act:
    d = os.path.dirname(c)
    if not os.path.exists(os.path.join(d, 'done.json')):
        n = len(glob.glob(os.path.join(d, 'b*.npz')))
        now.append('%s (%d batches)' % ('/'.join(d.split(os.sep)[-4:]), n))
print('running or claimed:', len(now))
for x in now:
    print('  ', x)
print('in plan %d, can start %d, finished %d, failures %d, failed 3x %d' % (len(plan), start, len(done), sum(len(v) for v in fails.values()), sum(len(v) >= 3 for v in fails.values())))
for d, v in fails.items():
    e = json.load(open(sorted(v)[-1]))
    print('FAILED %d: %s: %s' % (len(v), '/'.join(d.split(os.sep)[-4:]), e.get('error', '')[:160]))
