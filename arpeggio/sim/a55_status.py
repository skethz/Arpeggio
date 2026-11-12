#!/usr/bin/env python3
"""A5.5 progress from the saved results. Usage: a55_status.py ROOT"""
import glob, json, os, sys, collections
root = sys.argv[1]
plan = json.load(open(os.path.join(root, 'plan.json')))['jobs']
sel = json.load(open(os.path.join(root, 'select.json')))
st = collections.defaultdict(lambda: [0, 0.0, 0])
for f in glob.glob(os.path.join(root, '*', '*', '*', 'snr_*', 'done.json')):
    r = json.load(open(f)); k = (r['set'], r['shape'])
    st[k][0] += 1; st[k][1] += r['seconds'] / 3600
for j in plan:
    st[(j['set'], j['shape'])][2] += 1
run = sum(1 for j in plan if os.path.exists(os.path.join(root, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'claim.json')))
print('%-6s %-4s %6s %9s %7s' % ('set', 'shape', 'done', 'worker-h', 'queued'))
tot = 0.0
for k in sorted(st):
    print('%-6s %-4s %6d %9.2f %7d' % (k[0], k[1], st[k][0], st[k][1], st[k][2])); tot += st[k][1]
fails = len(glob.glob(os.path.join(root, '*', '*', '*', 'snr_*', 'failed.*.json')))
print('total worker-h %.1f | jobs running or claimed %d | failures logged %d | stage A complete %s | held-out final %s | picks %d | corners %d'
      % (tot, run, fails, sel.get('complete_a'), sel.get('heldout_final'), len(sel.get('per_s', {})), len(sel.get('corner', {}))))
