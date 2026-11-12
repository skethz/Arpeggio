#!/usr/bin/env python3
"""A5.4 analysis, PROTOCOL_A54.md section 4 (written 5 Nov 2026 after the series finished; the rule was fixed before any run).
No GPU. Usage: analyze_a54.py RESULTS_DIR A53_JSON   (RESULTS_DIR = .../results; A53_JSON = data/a5/a53.json, the Fig. 3 SA cycle ratios)
Writes RESULTS_DIR/a54/analysis.json.

Reported per point:
  - per Sk: uses, BER, ratio to (i) on the common prefix (paired cluster bootstrap, AN.boot_ratio) and McNemar;
    cycle ratio (L + F) / (L_128 + F_128) per K from a54/flips.json; its geometric mean over K (Fig. 3 plots this mean);
    the paired ratio to the next and the second-next doubling (saturation rule).
  - per SA S >= 4: the Sk whose geometric-mean cycle ratio is nearest SA's on a log scale, and the paired Antiphase/SA ratio on common uses.
Wording verdicts as section 4 states them."""
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

RES, A53 = sys.argv[1], json.load(open(sys.argv[2]))
FL = json.load(open(os.path.join(RES, 'a54', 'flips.json')))
PT = {'P1': dict(sh='x16', snr=20.0, Ns=32, bpu=64, grid=[32, 64, 128, 256, 512, 1024, 2048, 4096], ref='mdiane32',
                 sa=lambda S: 'abl_sa_32' if S == 128 else 'abl_sao_%d_32' % S, cyc='old'),
      'P2': dict(sh='x32', snr=22.0, Ns=8, bpu=128, grid=[32, 64, 128, 256, 512, 1024, 2048, 4096, 8192], ref='mdiane8',
                 sa=lambda S: 'abl_sas_%d_8' % S, cyc='sa2')}
SWEEPS = [4, 8, 16, 32, 64, 128]


def load(sub):
    fs = sorted(glob.glob(os.path.join(RES, sub, 'b*.npz')))
    if not fs:
        raise SystemExit('missing ' + sub)
    zs = [np.load(f, allow_pickle=False) for f in fs]
    idx = [int(os.path.basename(f)[1:6]) for f in fs]
    if idx != list(range(len(fs))):
        raise SystemExit('non-contiguous batches in ' + sub)
    return dict(biterr=np.concatenate([z['biterr'] for z in zs]).astype(np.int64), sizes=[len(z['biterr']) for z in zs],
                err_idx=[z['err_idx'] for z in zs], d_true=[z['d_true'] for z in zs])


def aligned(a, b):
    """Same draws check: equal batch sizes on the common batches, and equal true data on every use that is erroneous in both."""
    nb = min(len(a['sizes']), len(b['sizes']))
    if a['sizes'][:nb] != b['sizes'][:nb]:
        return False, 0
    checked = 0
    for i in range(nb):
        ia, ib = list(a['err_idx'][i]), list(b['err_idx'][i])
        com = sorted(set(ia) & set(ib))
        for u in com:
            if not np.array_equal(a['d_true'][i][ia.index(u)], b['d_true'][i][ib.index(u)]):
                return False, checked
            checked += 1
    return True, checked


def pair(a, b):
    n = min(len(a['biterr']), len(b['biterr']))
    r, lo, hi = AN.boot_ratio(a['biterr'][:n], b['biterr'][:n])
    p, x, y = AN.mcnemar(a['biterr'][:n], b['biterr'][:n])
    return dict(uses=n, ratio=r, lo=lo, hi=hi, mcnemar_p=p, only_first=x, only_second=y,
                err_first=int((a['biterr'][:n] > 0).sum()), err_second=int((b['biterr'][:n] > 0).sum()))


def geo(v):
    return float(math.exp(np.mean(np.log(v))))


out = dict(note='A5.4 analysis, PROTOCOL_A54.md section 4; exploratory; modeled cycles (L + F for Antiphase, S N + F_SA for SA, Fig. 3 data); '
                'cycle mean over K is geometric, as Fig. 3 plots it; seed 102, flips seed 1000.', points={})
for pt, p in PT.items():
    ref = load('abl/%s/%s/snr_%05.2f' % (p['sh'], p['ref'], p['snr']))
    arms = {Sk: load('a54/abl/%s/abl_anel_%d_%d/snr_%05.2f' % (p['sh'], Sk, p['Ns'], p['snr'])) for Sk in p['grid']}
    base = FL['%s/128' % p['sh']]
    rows = []
    for j, Sk in enumerate(p['grid']):
        a = arms[Sk]
        fk = FL['%s/%d' % (p['sh'], Sk)]
        cr = [(fk[K]['L'] + fk[K]['F']) / (base[K]['L'] + base[K]['F']) for K in ('1', '2', '3')]
        ok, nchk = aligned(a, ref)
        row = dict(Sk=Sk, uses=len(a['biterr']), err_uses=int((a['biterr'] > 0).sum()), bit_err=int(a['biterr'].sum()),
                   ber=float(a['biterr'].sum()) / (len(a['biterr']) * p['bpu']), cyc_ratio_K=cr, cyc_ratio=geo(cr),
                   vs_i=pair(a, ref), aligned_with_i=ok, aligned_checked=nchk)
        for d, lab in ((1, 'next'), (2, 'second')):
            if j + d < len(p['grid']):
                row['vs_' + lab] = pair(arms[p['grid'][j + d]], a)     # longer over this one
        rows.append(row)
    for row in rows:
        n1, n2 = row.get('vs_next'), row.get('vs_second')
        row['saturates'] = None if n1 is None or n2 is None else bool(n1['lo'] <= 1 <= n1['hi'] and
                                                                        (rows[rows.index(row) + 1]['vs_next']['lo'] <= 1 <= rows[rows.index(row) + 1]['vs_next']['hi']))
    sat = [r['Sk'] for r in rows if r['saturates']]
    match = []
    for S in SWEEPS:
        c = A53['cycles']['%s/%s/%d' % (p['sh'], p['cyc'], S)]
        sr = [c[K]['ratio'] for K in ('1', '2', '3')]
        m = geo(sr)
        best = min(rows, key=lambda r: abs(math.log(r['cyc_ratio']) - math.log(m)))
        sa = load('abl/%s/%s/snr_%05.2f' % (p['sh'], p['sa'](S), p['snr']))
        ok, nchk = aligned(arms[best['Sk']], sa)
        q = pair(arms[best['Sk']], sa)                                        # Antiphase over SA
        match.append(dict(S=S, sa_method=p['sa'](S), sa_cyc_ratio=m, sa_cyc_ratio_K=sr, Sk=best['Sk'], ap_cyc_ratio=best['cyc_ratio'],
                          cyc_mismatch=best['cyc_ratio'] / m, ap_over_sa=q, aligned=ok, aligned_checked=nchk,
                          sa_ber=float(sa['biterr'].sum()) / (len(sa['biterr']) * p['bpu']), sa_uses=len(sa['biterr'])))
    wins = []
    for mrow in match:
        if mrow['ap_over_sa']['hi'] < 1:
            wins.append(mrow['S'])
        else:
            break
    last = match[-1]['ap_over_sa']
    out['points'][pt] = dict(
        rows=rows, matched=match,
        verdict=dict(
            saturates_at=sat[0] if sat else None,
            antiphase_wins_equal_cycles_through_S=wins[-1] if wins else None,
            longer_sa_buys_lower_ber_holds=bool(last['lo'] > 1),
            largest_matched=dict(S=match[-1]['S'], Sk=match[-1]['Sk'], ratio=last['ratio'], lo=last['lo'], hi=last['hi'])))
json.dump(out, open(os.path.join(RES, 'a54', 'analysis.json'), 'w'), indent=1)
for pt, d in out['points'].items():
    print(pt, json.dumps(d['verdict']))
    for r in d['rows']:
        v = r['vs_i']
        print('  Sk %5d uses %6d err %4d BER %.3g  x %.2f [%s]  /(i) %.3f [%.3f, %.3f] p %.2g  next %s  sat %s  align %s/%d' % (
            r['Sk'], r['uses'], r['err_uses'], r['ber'], r['cyc_ratio'], ','.join('%.2f' % c for c in r['cyc_ratio_K']), v['ratio'], v['lo'], v['hi'],
            v['mcnemar_p'], ('%.2f [%.2f, %.2f]' % (r['vs_next']['ratio'], r['vs_next']['lo'], r['vs_next']['hi'])) if 'vs_next' in r else '-',
            r['saturates'], r['aligned_with_i'], r['aligned_checked']))
    for m in d['matched']:
        q = m['ap_over_sa']
        print('  S %3d x %.2f -> Sk %4d x %.2f (%.2fx)  AP/SA %.3f [%.3f, %.3f] p %.2g  uses %d err %d vs %d  align %s/%d' % (
            m['S'], m['sa_cyc_ratio'], m['Sk'], m['ap_cyc_ratio'], m['cyc_mismatch'], q['ratio'], q['lo'], q['hi'], q['mcnemar_p'], q['uses'],
            q['err_first'], q['err_second'], m['aligned'], m['aligned_checked']))
