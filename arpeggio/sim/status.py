#!/usr/bin/env python3
"""Status of a host's plan: per set, jobs done / running / failed / pending; running jobs with uses, errors and a
projected remaining time (from the batch times so far and the stopping rule); live workers.
Usage: status.py PLAN.json ROOT [--json OUT]"""
import json
import os
import sys
import time

import numpy as np

plan, root = json.load(open(sys.argv[1])), sys.argv[2]
SH = {'x16': (64, 156250), 'x32': (128, 78125), 'q16': (32, 312500), 'q32': (64, 156250)}
agg, running, failed = {}, [], []
now = time.time()
pend_est = 0.0
for j in plan['jobs']:
    d = os.path.join(root, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    a = agg.setdefault(j['set'], dict(total=0, done=0, running=0, failed=0, pending=0, cpu_h_done=0.0))
    a['total'] += 1
    bpu, cap = SH[j['shape']]
    cap = min(cap, int(j.get('max_bits', 1e7)) // bpu)
    if os.path.exists(os.path.join(d, 'done.json')):
        r = json.load(open(os.path.join(d, 'done.json')))
        a['done'] += 1; a['cpu_h_done'] += r['seconds'] / 3600
        continue
    if os.path.isdir(d) and any(f.startswith('failed.') for f in os.listdir(d)) and not os.path.exists(os.path.join(d, 'claim.json')):
        a['failed'] += 1; failed.append(d)
        continue
    if os.path.exists(os.path.join(d, 'claim.json')):
        a['running'] += 1
        n = ve = be = 0; sec = 0.0; last = 0
        for f in sorted(x for x in os.listdir(d) if x.startswith('b') and x.endswith('.npz')):
            z = np.load(os.path.join(d, f))
            x = z['biterr']; n += len(x); ve += int((x > 0).sum()); be += int(x.sum())
            inf = json.loads(str(z['info'])); sec += inf['seconds']; last = max(last, inf['t_end'])
        need = cap
        if n > 0 and ve > 0 and be > 0:
            need = min(cap, max(int(j.get('min_uses', 0)), int(n * 100 / ve) + 1, int(n * 100 / be) + 1))
        elif n > 0 and j.get('min_vec', 100) == 0:
            need = min(cap, int(j.get('min_uses', 0)))
        rate = sec / n if n else float('nan')
        rem = (need - n) * rate if n else float('nan')
        running.append(dict(job='%s/%s/%s/%.2f' % (j['set'], j['shape'], j['method'], j['snr']), uses=n, vec_err=ve, bit_err=be,
                            proj_uses=need, eta_h=round(rem / 3600, 2) if rem == rem else None,
                            idle_min=round((now - last) / 60, 1) if last else None,
                            worker=json.load(open(os.path.join(d, 'claim.json'))).get('worker')))
    else:
        a['pending'] += 1
print(time.strftime('%Y-%m-%d %H:%M:%S'), plan['host'])
for k, v in agg.items():
    print('  %-6s total %4d done %4d running %3d failed %3d pending %4d  (solver-hours done %.1f)' % (
        k, v['total'], v['done'], v['running'], v['failed'], v['pending'], v['cpu_h_done']))
for r in running:
    print('  RUN', json.dumps(r))
for f in failed:
    print('  FAILED', f)
if '--json' in sys.argv:
    json.dump(dict(t=now, host=plan['host'], sets=agg, running=running, failed=failed), open(sys.argv[sys.argv.index('--json') + 1], 'w'))
