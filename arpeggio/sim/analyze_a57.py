#!/usr/bin/env python3
"""Amendment 7 analysis (PROTOCOL_A57.md section 5; written 6 Nov 2026 before any HQ result). No GPU.
Usage: analyze_a57.py ROOT   (ROOT = .../results/a56; reads ROOT/select.json, HN and HQ). Writes ROOT/analysis_a57.json.
First-accept SA (rule (2), apx55 'abl_far_*') and Antiphase's HN pick, both with the same first-pass stop at the c of select.json,
on the same draws (seed 102). Cost per anneal at K: first-accept SA (tests + flips) / anneals (A5.5 model F = C_FA, measured on the
run); Antiphase L_K + F_K (a56an.cyc_table, as amendment 4). Ratio SA/Antiphase of bit errors on the common prefix, paired cluster
bootstrap (a56an.boot_ratio) and exact McNemar on erroneous uses. x = mean modeled cycles SA / Antiphase on the same uses."""
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

ROOT = sys.argv[1]
PT = {'P1': dict(sh='x16', snr=20.0, bpu=64, Rmax=3), 'P2': dict(sh='x32', snr=22.0, bpu=128, Rmax=3)}
XMAX = 1.10


def tests_per_K(d):
    tot = {}
    for f in sorted(glob.glob(os.path.join(d, 'b*.npz'))):
        info = json.loads(str(np.load(f, allow_pickle=False)['info']))
        c = info.get('cnt', {})
        c = c.get('cnt', c) if isinstance(c, dict) else {}
        for K, v in c.items():
            t = tot.setdefault(str(K), dict(tests=0.0, flips=0.0, anneals=0.0))
            t['tests'] += float(v.get('tests', 0)); t['flips'] += float(v.get('flips', 0.0)); t['anneals'] += float(v.get('anneals', 0.0))
    return tot


def cyc_far(d, Rmax):
    tot = tests_per_K(d)
    out = []
    for K in range(1, Rmax + 1):
        v = tot.get(str(K))
        if not v or not v['anneals'] or not v['tests']:
            raise SystemExit('no first-accept test counts for K=%d in %s' % (K, d))
        out.append((v['tests'] + v['flips']) / v['anneals'])
    return np.array(out)


def term(lo, hi):
    return 'antiphase_leads' if lo > 1 else ('sa_leads' if hi < 1 else 'no_detected_difference')


sel = json.load(open(os.path.join(ROOT, 'select.json')))
res = dict(note='Amendment 7: first-accept SA (model F) and Antiphase, both with the same stop and more anneals; modeled cycles only; '
                'exploratory; seed 102; ratio = SA / Antiphase.', points={})
for pt, p in PT.items():
    cp = sel['c'][pt]['c']
    apm = sel['N'][pt]['pick']['method']
    sub = lambda st, m: os.path.join(ROOT, st, p['sh'], m, 'snr_%05.2f' % p['snr'])
    ap = AN.load(sub('HN', apm))
    cya = AN.cyc_table(ap, p['Rmax'])
    bea, Ca, firsta = AN.stop(ap, cp, cya)
    rows = {}
    hq = os.path.join(ROOT, 'HQ', p['sh'])
    for m in sorted(os.listdir(hq)) if os.path.isdir(hq) else []:
        d = sub('HQ', m)
        if not os.path.exists(os.path.join(d, 'done.json')):
            continue
        r = AN.load(d)
        cy = cyc_far(d, p['Rmax'])
        be, C, first = AN.stop(r, cp, cy)
        n = min(len(be), len(bea))
        if r['sizes'][:len(ap['sizes'])] != ap['sizes'][:len(r['sizes'])]:
            raise SystemExit('batch sizes differ, draws not paired: ' + m)
        q = AN.boot_ratio(be[:n], bea[:n])
        q0 = AN.boot_ratio(r['biterr'][:n].astype(np.int64), ap['biterr'][:n].astype(np.int64))
        pm, so, ao = AN.mcnemar(be[:n], bea[:n])
        x = float(C[:n].mean() / Ca[:n].mean())
        rows[m] = dict(c=cp, uses=n, antiphase=apm, ratio=q[0], lo=q[1], hi=q[2], term=term(q[1], q[2]), mcnemar_p=pm, sa_only=so, ap_only=ao,
                       sa_err_uses=int((be[:n] > 0).sum()), ap_err_uses=int((bea[:n] > 0).sum()), sa_bit_err=int(be[:n].sum()), ap_bit_err=int(bea[:n].sum()),
                       x=x, within_budget=bool(x <= XMAX), sa_cyc=float(C[:n].mean()), ap_cyc=float(Ca[:n].mean()),
                       sa_p99=float(np.percentile(C[:n], 99)), ap_p99=float(np.percentile(Ca[:n], 99)), sa_max=float(C[:n].max()), ap_max=float(Ca[:n].max()),
                       sa_stop0=float((first[:n] == 0).mean()), ap_stop0=float((firsta[:n] == 0).mean()),
                       nostop_ratio=q0[0], nostop_lo=q0[1], nostop_hi=q0[2], sa_cyc_per_anneal=cy.tolist(), ap_cyc_per_anneal=cya.tolist(),
                       ber_sa=float(be[:n].sum()) / (n * p['bpu']), ber_ap=float(bea[:n].sum()) / (n * p['bpu']))
    inb = [v for v in rows.values() if v['within_budget']]
    if len(rows) < 2:
        verdict = 'incomplete'
    elif inb and all(v['term'] == 'antiphase_leads' for v in inb):
        verdict = 'antiphase_leads'
    elif any(v['term'] == 'sa_leads' for v in inb):
        verdict = 'sa_leads'
    else:
        verdict = 'no_detected_difference' if inb else 'no_arm_within_budget'
    res['points'][pt] = dict(c=cp, antiphase=apm, arms=rows, verdict=verdict)
v = [res['points'][pt]['verdict'] for pt in PT]
res['verdict'] = dict(per_point=dict(zip(PT, v)), both_antiphase=all(x == 'antiphase_leads' for x in v))
json.dump(res, open(os.path.join(ROOT, 'analysis_a57.json'), 'w'), indent=1)
for pt, d in res['points'].items():
    print(pt, 'c', d['c'], 'AP', d['antiphase'], 'verdict', d['verdict'])
    for m, r in d['arms'].items():
        print('  %-34s SA/AP %.3f [%.3f, %.3f] %s  McNemar p %.2g (%d vs %d)  x %.2f  err %d vs %d  uses %d  p99 %.0f vs %.0f  nostop %.2f' % (
            m, r['ratio'], r['lo'], r['hi'], r['term'], r['mcnemar_p'], r['sa_only'], r['ap_only'], r['x'], r['sa_err_uses'], r['ap_err_uses'], r['uses'],
            r['sa_p99'], r['ap_p99'], r['nostop_ratio']))
print('VERDICT', json.dumps(res['verdict']))
