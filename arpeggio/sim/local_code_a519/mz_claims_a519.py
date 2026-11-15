#!/usr/bin/env python3
"""A5.19 share with hostB. Runs on hostA: hostA's results tree is the one place that decides which
host runs a held-out chunk.
  take N KEEP     walk hostA's plan.json from the end and take up to N held-out chunks (sets h4_*/h1_*) that have no done.json, no
                  claim.json and fewer than 3 failures; each gets an exclusive claim.json owned by hostB (O_EXCL, as trace_a56.claim).
                  Stops while KEEP or fewer such chunks would be left for hostA. hostA's workers never take a chunk claimed by another
                  host; pid 1 makes hostA's planner count it as busy. Prints the taken jobs, one JSON line each.
                  Every free S* calibration job (set 'calib') is also taken for hostB, all at once and before
                  the held-out chunks, so the whole calibration runs on one host (hostB). Stage A and stage B are never handed out.
  release SET METHOD   rename hostB's claim on that chunk to claim.released.<t> (manual: e.g. after a long yield on hostB).
  list            hostB-owned chunks: open or done, and how many batch files hostA has. No results are read."""
import glob
import json
import os
import sys
import time

Z = os.environ.get('MZ_ROOT', '<SCRATCH>/arpeggio_ber_20261024/a519z/results/a519')
OWNER = 'hostB-share'


def jd(j):
    return os.path.join(Z, j['set'], j['shape'], j['method'], 'snr_%05.2f' % float(j['snr']))


def held(j):
    return j['set'].startswith(('h4_', 'h1_'))


def free(j):
    d = jd(j)
    if os.path.exists(os.path.join(d, 'done.json')) or os.path.exists(os.path.join(d, 'claim.json')):
        return False
    return not (os.path.isdir(d) and sum(f.startswith('failed.') for f in os.listdir(d)) >= 3)


mode = sys.argv[1]
def own(j):
    d = jd(j)
    os.makedirs(d, exist_ok=True)
    try:
        fd = os.open(os.path.join(d, 'claim.json'), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, json.dumps(dict(worker=OWNER, host='hostB', pid=1, t=time.time(), note='A519M: run on hostB')).encode())
    os.close(fd)
    return True


if mode == 'take':
    n, keep = int(sys.argv[2]), int(sys.argv[3])
    jobs = json.load(open(os.path.join(Z, 'plan.json')))['jobs']
    for j in jobs:                                                     # all free calibration jobs, first
        if j['set'] == 'calib' and free(j) and own(j):
            print(json.dumps(j))
    cand = [j for j in jobs if held(j) and free(j)]
    took = 0
    for j in reversed(cand):
        if took >= n or len(cand) - took <= keep:
            break
        if own(j):
            print(json.dumps(j))
            took += 1
elif mode == 'release':
    st, m = sys.argv[2], sys.argv[3]
    for d in glob.glob(os.path.join(Z, st, '*', m, 'snr_*')):
        cf = os.path.join(d, 'claim.json')
        if os.path.exists(cf) and json.load(open(cf)).get('worker') == OWNER and not os.path.exists(os.path.join(d, 'done.json')):
            os.rename(cf, cf + '.released.%d' % int(time.time()))
            print('released', os.path.relpath(d, Z))
elif mode == 'list':
    for cf in sorted(glob.glob(os.path.join(Z, '*_c*', '*', '*', 'snr_*', 'claim.json'))):
        try:
            if json.load(open(cf)).get('worker') != OWNER:
                continue
        except Exception:
            continue
        d = os.path.dirname(cf)
        print(os.path.relpath(d, Z), 'done' if os.path.exists(os.path.join(d, 'done.json')) else 'open',
              len(glob.glob(os.path.join(d, 'b*.npz'))))
else:
    sys.exit('usage: take N KEEP | release SET METHOD | list')
