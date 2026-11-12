#!/usr/bin/env python3
"""A5.12 selection (PROTOCOL_A512.md section 2): for each c, once all 18 P1 cells are done, the pick by fewest bit errors, then
fewest erroneous uses, then grid order (A5 cells first). Writes pt12_c<k> into tuned_a512.json and a512_sel.json; a pick is
never overwritten. Exit 10 if a pick was written, else 0. Usage: select_a512.py ROOT"""
import json, os, sys
root = sys.argv[1]
plan = json.load(open(os.path.join(root, 'plan_a512.json')))
selp, tp = os.path.join(root, 'a512_sel.json'), os.path.join(root, 'tuned_a512.json')
sel = json.load(open(selp)) if os.path.exists(selp) else {}
new = False
for c in (5, 3, 2):
    key = 'pt12_c%d' % c
    if key in sel:
        continue
    cells = [j for j in plan['jobs'] if j['set'] == 'tune' and j['method'].startswith('abl_ptt_c%d_' % c)]
    assert len(cells) == 18
    rows = []
    for i, j in enumerate(cells):
        d = os.path.join(root, 'tune', j['shape'], j['method'], 'snr_%05.2f' % j['snr'], 'done.json')
        if not os.path.exists(d):
            break
        r = json.load(open(d))
        a = j['method'].split('_')
        T0, T1 = float(a[3]), float(a[4])
        rows.append(((r['bit_err'], r['vec_err'], i), dict(T0=T0, T1=T1, source=j['method'], bit_err=r['bit_err'], vec_err=r['vec_err'],
                                                          uses=r['uses'], corner=bool(T0 == 0.075 or T1 == 0.0125))))
    if len(rows) != 18:
        continue
    k, v = min(rows, key=lambda t: t[0])
    v['cells'] = {w['source']: [w['bit_err'], w['vec_err']] for _, w in rows}
    sel[key] = v
    new = True
if new:
    tuned = json.load(open(tp))
    for k, v in sel.items():
        tuned[k] = dict(T0=v['T0'], T1=v['T1'], source=v['source'])
    json.dump(tuned, open(tp + '.tmp', 'w'), indent=1); os.replace(tp + '.tmp', tp)
    json.dump(sel, open(selp + '.tmp', 'w'), indent=1); os.replace(selp + '.tmp', selp)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'cells'} for k, v in sel.items()}))
    sys.exit(10)
sys.exit(0)
