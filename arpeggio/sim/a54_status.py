#!/usr/bin/env python3
"""A5.4 progress: one line per job from the saved batches. Also prints 'total done startable' for the supervisor with --brief.
Usage: a54_status.py PLAN ROOT [--brief]"""
import glob, json, os, sys, numpy as np
plan, root = json.load(open(sys.argv[1])), sys.argv[2]; brief = '--brief' in sys.argv
alive = lambda p: os.path.exists('/proc/%d' % p)
tot = done = start = 0
for j in plan['jobs']:
    d = os.path.join(root, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr']); tot += 1
    st = 'waiting'; cl = os.path.join(d, 'claim.json')
    if os.path.exists(os.path.join(d, 'done.json')):
        st = 'done'; done += 1
    elif len(glob.glob(os.path.join(d, 'failed.*.json'))) >= 3:
        st = 'FAILED 3x'
    elif os.path.exists(cl):
        try:
            st = 'running' if alive(int(json.load(open(cl))['pid'])) else 'stale'
        except Exception:
            st = 'running'
        start += st == 'stale'
    else:
        start += 1
    if brief:
        continue
    n = ve = be = 0; sec = 0.0
    for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
        z = np.load(f, allow_pickle=False); x = z['biterr']
        n += len(x); ve += int((x > 0).sum()); be += int(x.sum()); sec += float(json.loads(str(z['info']))['seconds'])
    bpu = 64 if j['shape'] == 'x16' else 128
    print('%-4s %-18s %-9s uses %7d  err uses %4d  bit err %6d  BER %s  %6.1f h' % (j['point'], j['method'], st, n, ve, be, '%.2e' % (be / (n * bpu)) if n else '  -   ', sec / 3600))
print(tot, done, start)
