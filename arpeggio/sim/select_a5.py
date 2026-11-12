#!/usr/bin/env python3
"""A5 tuning selections (seed 1000; 4,000 uses per cell at P1/P3, 2,000 at P2; rule of PROTOCOL 4.3: fewest bit errors,
then fewest erroneous uses, then plan order). Each family is selected once, when all its cells are done, into
results/a5_sel_<family>.json (never overwritten); tuned_a5.json is the merged view (derived; rewritten on every call).
Families: pt (pt_cyc, pt_fl at P1; pt_cyc_<shape>, pt_fl_<shape> at P2/P3), sa2, colx16 / colx32 (per m; flags col_x16 / col_x32), dim, symd,
qdim_pp (per shape). Usage: select_a5.py ROOT PLAN [family ...]   (no family: merge only). Exit 10 if a new selection was written."""
import json, os, sys
root, planf = sys.argv[1:3]
fams = sys.argv[3:]
plan = json.load(open(planf))
tj = [(i, j) for i, j in enumerate(plan['jobs']) if j['set'] == 'tune']
old = os.path.join(root, 'tune')


def res(j):
    d = os.path.join(root, 'tune', j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json')
    return json.load(open(d)) if os.path.exists(d) else None


def family_of(j):
    m, sh = j['method'], j['shape']
    a = m[4:].rsplit('_', 1)[0].split('_')
    if a[0] == 'ptt':
        return 'pt', ('pt_' + a[1]) if sh == 'x16' else ('pt_%s_%s' % (a[1], sh)), dict(T0=float(a[2]), T1=float(a[3]))
    if a[0] == 'sat':
        return 'sa2', 'sa2', dict(T0=float(a[1]), T1=float(a[2]))
    if a[0] == 'colt':
        return 'col' + sh, (sh, a[1]), dict(q=float(a[2]), T=float(a[3]))
    if a[0] == 'dimt':
        return 'dim', 'dim', dict(q=float(a[1]), T=float(a[2]))
    if a[0] == 'symdt':
        return 'symd', 'symd', dict(T=float(a[1]), q=float(a[2]))
    if a[0] == 'qdimc' and j.get('a5'):
        return 'qdim_pp', sh, dict(c=float(a[1]), q0=float(a[2]), T=float(a[3]))
    return None, None, None


new = False
for fam in fams:
    out = os.path.join(root, 'a5_sel_%s.json' % fam)
    if os.path.exists(out):
        continue
    pick = {}
    unfinished = False
    for i, j in tj:
        f, key, par = family_of(j)
        if f != fam:
            continue
        r = res(j)
        if r is None:
            unfinished = True
            break
        k = (r['bit_err'], r['vec_err'], i)
        kk = json.dumps(key)
        if kk not in pick or k < pick[kk][0]:
            pick[kk] = (k, dict(par, source=j['method'], shape=j['shape'], bit_err=r['bit_err'], vec_err=r['vec_err']))
    if unfinished or not pick:
        continue
    new = True
    sel = {}
    for kk, (_, v) in pick.items():
        key = json.loads(kk)
        if fam.startswith('col'):
            sel.setdefault('col', {}).setdefault(key[0], {})[key[1]] = v
            sel[fam.replace('col', 'col_')] = True
        elif fam == 'qdim_pp':
            sel.setdefault('qdim_pp', {})[key] = v
        else:
            sel[key] = v
    json.dump(sel, open(out, 'w'), indent=1)
    print(fam, json.dumps(sel, indent=1))
merged = {'sa': json.load(open(os.path.join(root, 'tuned.json')))['sa']}
for f in sorted(os.listdir(root)):
    if f.startswith('a5_sel_') or f == 'a5_flip_phi.json':
        d = json.load(open(os.path.join(root, f)))
        if f == 'a5_flip_phi.json':
            merged['flip_phi'] = d['flip_phi']
        else:
            for k, v in d.items():
                if k == 'col':
                    merged.setdefault('col', {}).update(v)
                else:
                    merged[k] = v
json.dump(merged, open(os.path.join(root, 'tuned_a5.json'), 'w'), indent=1)
print('merged keys', sorted(merged))
sys.exit(10 if new else 0)
