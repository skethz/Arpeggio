#!/usr/bin/env python3
"""A5.21 plan. Pure function of saved results: writes ROOT/plan.json (jobs that can run now, in queue
order) and ROOT/select.json (gates, held_done). Gates G1-G4 first (seed 102, batch 0, worker 'saved' check); held-out chunks only after all
four gates are done. Held-out: seed 2028; P1 batches 0-149 x 2,000 uses, P2 batches 0-299 x 1,000 uses; chunks of 10, interleaved by
fraction of the run across the four arms. Usage: a521_plan.py ROOT   (ROOT = .../a521/results/a521)"""
import glob, json, os, sys
ROOT = sys.argv[1]
A = '<SCRATCH>/arpeggio_ber_20261024'
P1 = dict(pt='P1', sh='x16', snr=20.0, B=2000, N=150, CH=10)
P2 = dict(pt='P2', sh='x32', snr=22.0, B=1000, N=300, CH=10)
HSEED = 2028
ARMS = [(P1, 'C0', 'mdichord32'), (P1, 'SA', 'abl_fam_4_0.3_0.15_rand_32'),
        (P2, 'C0', 'mdichord8'), (P2, 'SA', 'abl_fam_2_0.2_0.2_bal_8')]
GATES = [('g1', P1, 'abl_fam_4_0.3_0.15_rand_32', A + '/results/a55/abl/x16/abl_fam_4_0.3_0.15_rand_32/snr_20.00'),
         ('g2', P2, 'abl_fam_2_0.2_0.2_bal_8', A + '/results/a55/abl/x32/abl_fam_2_0.2_0.2_bal_8/snr_22.00'),
         ('g3', P2, 'mdichord8', A + '/results/abl/x32/mdichord8/snr_22.00'),
         ('g4', P1, 'mdichord32', A + '/results/abl/x16/mdichord32/snr_20.00')]


def jdir(st, p, m):
    return os.path.join(ROOT, st, p['sh'], m, 'snr_%05.2f' % p['snr'])


def done(st, p, m):
    return os.path.exists(os.path.join(jdir(st, p, m), 'done.json'))


def failed3(st, p, m):
    return len(glob.glob(os.path.join(jdir(st, p, m), 'failed.*.json'))) >= 3


def job(st, p, m, **kw):
    j = dict(set=st, shape=p['sh'], method=m, snr=p['snr'], batch=p['B'], point=p['pt'])
    j.update(kw)
    return j


plan, sel = [], dict(gates={}, gate_failed=[], held={}, held_done=False)
for g, p, m, sv in GATES:
    sel['gates'][g] = done(g, p, m)
    if failed3(g, p, m):
        sel['gate_failed'].append(g)
    elif not sel['gates'][g]:
        plan.append(job(g, p, m, seed=102, first_batch=0, n_batches=1, saved=sv))
gates_ok = all(sel['gates'].values())
held = []
for i, (p, k, m) in enumerate(ARMS):
    sel['held']['%s/%s' % (p['pt'], k)] = m
    nch = (p['N'] + p['CH'] - 1) // p['CH']
    for c in range(nch):
        st = 'h_%s_c%03d' % (p['pt'], c)
        j = job(st, p, m, seed=HSEED, first_batch=p['CH'] * c, n_batches=min(p['CH'], p['N'] - p['CH'] * c))
        held.append(((c + 0.5) / nch, i, j, p))
hd = all(done(j['set'], p, j['method']) for _, _, j, p in held)
if gates_ok and not sel['gate_failed']:
    for _, _, j, p in sorted(held, key=lambda t: (t[0], t[1])):
        if not done(j['set'], p, j['method']) and not failed3(j['set'], p, j['method']):
            plan.append(j)
sel['held_done'] = bool(gates_ok and hd)
sel['stop'] = bool(sel['gate_failed'])
for fn, obj in (('plan.json', dict(host='hostB', experiment='A5.21', jobs=plan)), ('select.json', sel)):
    tmp = os.path.join(ROOT, fn + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, os.path.join(ROOT, fn))
print(len(plan), int(gates_ok), int(sel['held_done']))
