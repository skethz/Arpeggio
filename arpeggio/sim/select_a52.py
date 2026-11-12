#!/usr/bin/env python3
"""A5.2 selection: for each budget (cyc, fl) and point, the pick over the union of the frozen 12 cells (plan_hostb_a5.json)
and the 6 extension cells (plan_hostb_a52.json), by the same rule (fewest bit errors, then erroneous uses, then order:
frozen cells first). Writes a52_sel.json once (refuses to overwrite) and tuned_a52.json (= tuned_a5.json + pt2_* keys).
Exit 10 when written, 0 if not all cells are done. Usage: select_a52.py ROOT"""
import json, os, sys
root = sys.argv[1]
out = os.path.join(root, 'a52_sel.json')
if os.path.exists(out):
    sys.exit(0)
cells = [j for j in json.load(open(os.path.join(root, 'plan_hostb_a5.json')))['jobs'] if j['set'] == 'tune' and j['method'].startswith('abl_ptt_')]
cells += [j for j in json.load(open(os.path.join(root, 'plan_hostb_a52.json')))['jobs'] if j['set'] == 'tune']
pick, frozen = {}, {}
for i, j in enumerate(cells):
    d = os.path.join(root, 'tune', j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json')
    if not os.path.exists(d):
        sys.exit(0)
    r = json.load(open(d))
    a = j['method'].split('_')
    key = 'pt2_' + a[2] + ('' if j['shape'] == 'x16' else '_' + j['shape'])
    k = (r['bit_err'], r['vec_err'], i)
    v = dict(T0=float(a[3]), T1=float(a[4]), source=j['method'], bit_err=r['bit_err'], vec_err=r['vec_err'], extension=bool(j.get('a52')))
    if key not in pick or k < pick[key][0]:
        pick[key] = (k, v)
sel = {k: v for k, (_, v) in pick.items()}
tuned = json.load(open(os.path.join(root, 'tuned_a5.json')))
for k, v in sel.items():
    old = tuned.get(k.replace('pt2_', 'pt_'))
    v['frozen_pick'] = None if old is None else dict(T0=old['T0'], T1=old['T1'], source=old.get('source'))
    v['changed'] = bool(old is None or (old['T0'], old['T1']) != (v['T0'], v['T1']))
json.dump(sel, open(out, 'w'), indent=1)
tuned.update(sel)
json.dump(tuned, open(os.path.join(root, 'tuned_a52.json'), 'w'), indent=1)
print(json.dumps(sel, indent=1))
sys.exit(10)
