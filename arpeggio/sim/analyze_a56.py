#!/usr/bin/env python3
"""A5.6 analysis (PROTOCOL_A56.md section 9). No GPU. Reads what exists; a missing part is left out. Writes ROOT/analysis.json. Usage: analyze_a56.py ROOT"""
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

ROOT = sys.argv[1]
RES = os.path.dirname(os.path.abspath(ROOT))
PT = {'P1': dict(sh='x16', snr=20.0, Ns=32, bpu=64, Rmax=3), 'P2': dict(sh='x32', snr=22.0, Ns=8, bpu=128, Rmax=3),
      'P3': dict(sh='q32', snr=14.0, Ns=8, bpu=64, Rmax=1), 'P4': dict(sh='x16', snr=31.02, Ns=8, bpu=64, Rmax=3)}
BASE = lambda pt: 'a56_128_0.3_0.3_0.4_0_alt_%d' % PT[pt]['Ns']


def run(st, pt, m):
    p = PT[pt]
    return AN.load(os.path.join(ROOT, st, p['sh'], m, 'snr_%05.2f' % p['snr']))


def saved_biterr(sub):
    fs = sorted(glob.glob(os.path.join(RES, sub, 'b*.npz')))
    if not fs:
        return None
    return dict(biterr=np.concatenate([np.load(f, allow_pickle=False)['biterr'] for f in fs]))


def stop_section(r, pt, c_pick):
    cyc = AN.cyc_table(r, PT[pt]['Rmax'])
    out = dict(uses=len(r['biterr']), cyc_per_anneal=cyc.tolist(), ber=float(r['biterr'].astype(np.int64).sum()) / (len(r['biterr']) * PT[pt]['bpu']),
               t0_mean=float(r['t'][:, 0].mean()), rows=[AN.stop_row(r, c, cyc) for c in AN.C_GRID])
    if c_pick is not None:
        out['n0'] = [AN.stop_row(r, c_pick, cyc, d) for d in (-1.0, 1.0)]
    S = r['t'].shape[1] - 1
    C = np.concatenate([np.zeros((len(r['t']), 1)), np.cumsum((r['ann'] * cyc).sum(-1), 1)], 1)
    out['by_stage'] = [dict(stages=j, ber=float(r['be'][:, j].astype(np.int64).sum()) / (len(r['t']) * PT[pt]['bpu']), err_uses=int((r['be'][:, j] > 0).sum()),
                            cyc=float(C[:, j].mean())) for j in range(S + 1)]
    ann = r['ann'].sum((0, 1)).astype(np.float64)
    win = r['win']
    out['per_K'] = [dict(K=K, anneal_share=float(ann[K - 1] / max(ann.sum(), 1)), cycle_share=float(ann[K - 1] * cyc[K - 1] / max((ann * cyc).sum(), 1)),
                         wins=int((win == K).sum())) for K in range(1, PT[pt]['Rmax'] + 1)]
    return out


res = dict(stop={}, tune={}, held={}, others={}, lengths={})
sel = json.load(open(os.path.join(ROOT, 'select.json'))) if os.path.exists(os.path.join(ROOT, 'select.json')) else {}
refs = {}
for pt in PT:
    a = run('A', pt, BASE(pt))
    c = sel.get('c', {}).get(pt, {}).get('c')
    sec = {}
    if a is not None:
        sec['tuning'] = stop_section(a, pt, c)
        sec['c_pick'] = c
    h = run('R3' if pt == 'P3' else 'R', pt, BASE(pt))
    x3f = run('X3F', pt, BASE(pt)) if pt in ('P1', 'P2') else run('R3X', pt, BASE(pt)) if pt == 'P3' else None
    if h is not None and x3f is not None and len(h['biterr']) == {'P1': 20000, 'P2': 43000, 'P3': 632000}[pt]:   # same stream, batches continue the saved series
        for k in ('biterr', 't', 'be', 'ann', 'rad', 'win'):
            h[k] = np.concatenate([h[k], x3f[k]], 0)
        for K, v in x3f['cnt'].items():
            c0 = h['cnt'].setdefault(K, dict(flips=0.0, anneals=0.0))
            c0['flips'] += v['flips']; c0['anneals'] += v['anneals']
    if h is not None:
        refs[pt] = h
        sec['heldout'] = stop_section(h, pt, c)
    res['stop'][pt] = sec
    if a is None:
        continue
    cy0 = AN.cyc_table(a, PT[pt]['Rmax'])
    for st in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, st, PT[pt]['sh'])
        if st not in ('F', 'D', 'C1', 'C2', 'B', 'J', 'N', 'G') or not os.path.isdir(d):   # tuning-seed arms only
            continue
        for m in sorted(os.listdir(d)):
            r = run(st, pt, m)
            if r is None or (st == 'A'):
                continue
            row = AN.paired_row(r, a, PT[pt]['bpu'], name=m, cyc_arm=AN.cyc_table(r, r['ann'].shape[-1]), cyc_ref=cy0)
            res['tune'].setdefault(pt, {}).setdefault(st, []).append(row)
    if pt not in refs:
        continue
    ref = refs[pt]
    cyr = AN.cyc_table(ref, PT[pt]['Rmax'])
    for st in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, st, PT[pt]['sh'])
        if not (st == 'L' or st.startswith('H')) or not os.path.isdir(d):
            continue
        for m in sorted(os.listdir(d)):
            r = run(st, pt, m)
            if r is None:
                continue
            cy = AN.cyc_table(r, r['ann'].shape[-1])
            row = AN.paired_row(r, ref, PT[pt]['bpu'], name=m, cyc_arm=cy, cyc_ref=cyr)
            cpk = sel.get('c', {}).get(pt, {}).get('c')
            if cpk is not None:
                be, C, _ = AN.stop(r, cpk, cy)
                n = min(len(be), len(ref['biterr']))
                q = AN.boot_ratio(be[:n], ref['biterr'][:n].astype(np.int64))
                row['with_stop'] = dict(c=cpk, ratio=q[0], lo=q[1], hi=q[2], x_cycles=float(C[:n].mean() / max(AN.nostop_cycles(ref, cyr)[:n].mean(), 1e-9)), err_uses=int((be[:n] > 0).sum()))
                for label, sub in (('sa', 'abl/%s/abl_sa_%d/snr_%05.2f' % (PT[pt]['sh'], PT[pt]['Ns'], PT[pt]['snr'])), ('kbest', 'abl/%s/kbest32/snr_%05.2f' % (PT[pt]['sh'], PT[pt]['snr']))):
                    sv = saved_biterr(sub)
                    if sv is not None:
                        n2 = min(len(be), len(sv['biterr']))
                        q2 = AN.boot_ratio(sv['biterr'][:n2].astype(np.int64), be[:n2])
                        row['with_stop']['saved_' + label + '_over_arm'] = dict(uses=n2, ratio=q2[0], lo=q2[1], hi=q2[2])
            for label, sub in (('sa', 'abl/%s/abl_sa_%d/snr_%05.2f'), ('kbest', 'abl/%s/kbest32/snr_%05.2f')):
                sv = saved_biterr(sub % ((PT[pt]['sh'], PT[pt]['Ns'], PT[pt]['snr']) if label == 'sa' else (PT[pt]['sh'], PT[pt]['snr'])))
                if sv is not None:
                    n = min(len(r['biterr']), len(sv['biterr']))
                    q = AN.boot_ratio(sv['biterr'][:n].astype(np.int64), r['biterr'][:n].astype(np.int64))
                    row['saved_' + label + '_over_arm'] = dict(uses=n, ratio=q[0], lo=q[1], hi=q[2])
            res['held'].setdefault(pt, {}).setdefault(st, []).append(row)
    # frozen schedule at other lengths, from A5.4, on the same draws
    for r0 in res['held'].get(pt, {}).get('HG', []):
        m = r0['name']
        Sk = int(m.split('_')[1])
        sv = saved_biterr('a54/abl/%s/abl_anel_%d_%d/snr_%05.2f' % (PT[pt]['sh'], Sk, PT[pt]['Ns'], PT[pt]['snr']))
        r = run('HG', pt, m)
        if sv is not None:
            n = min(len(r['biterr']), len(sv['biterr']))
            q = AN.boot_ratio(r['biterr'][:n].astype(np.int64), sv['biterr'][:n].astype(np.int64))
            r0['vs_frozen_same_length'] = dict(uses=n, ratio=q[0], lo=q[1], hi=q[2], frozen_err_uses=int((sv['biterr'][:n] > 0).sum()))
    # the same test on the other solvers: full traces where they exist; start-only on saved runs
    cp = sel.get('c', {}).get(pt, {}).get('c')
    if cp is not None:
        for st, m in (('S', 'abl_sa_%d' % PT[pt]['Ns']), ('S', 'mdiahc%d' % PT[pt]['Ns'])):
            r = run(st, pt, m)
            if r is not None:
                cy = np.arange(1, PT[pt]['Rmax'] + 1, dtype=np.float64)    # cost per anneal taken as proportional to K (rough): saving only
                res['others'].setdefault(pt, {})[m] = AN.stop_row(r, cp, cy)
        thr = ref['Nr'] + cp * math.sqrt(ref['Nr'])
        for m in ('abl_sa_%d' % PT[pt]['Ns'], 'mdiahc%d' % PT[pt]['Ns'], 'abl_sa2_%d' % PT[pt]['Ns'], 'abl_ons_%d' % PT[pt]['Ns']):
            sv = saved_biterr('abl/%s/%s/snr_%05.2f' % (PT[pt]['sh'], m, PT[pt]['snr']))
            if sv is None:
                continue
            n = min(len(sv['biterr']), len(ref['biterr']))
            pas = ref['t'][:n, 0] <= thr
            be = np.where(pas, ref['be'][:n, 0], sv['biterr'][:n]).astype(np.int64)
            q = AN.boot_ratio(be, sv['biterr'][:n].astype(np.int64))
            res['others'].setdefault(pt, {})[m + '/start_only'] = dict(c=cp, uses=n, stop0=float(pas.mean()), ratio=q[0], lo=q[1], hi=q[2], ber=float(be.sum()) / (n * PT[pt]['bpu']),
                                                                         ber_nostop=float(sv['biterr'][:n].astype(np.int64).sum()) / (n * PT[pt]['bpu']))
# amendment 4: SA and Antiphase, both with the stop at the same c and more anneals, same draws
for pt in ('P1', 'P2'):
    cp = sel.get('c', {}).get(pt, {}).get('c')
    pk = sel.get('N', {}).get(pt, {}).get('pick')
    d = os.path.join(ROOT, 'HR', PT[pt]['sh'])
    if cp is None or not pk or not os.path.isdir(d):
        continue
    ap = run('HN', pt, pk['method'])
    if ap is None:
        continue
    cya = AN.cyc_table(ap, PT[pt]['Rmax'])
    bea, Ca, _ = AN.stop(ap, cp, cya)
    for m in sorted(os.listdir(d)):
        r = run('HR', pt, m)
        if r is None:
            continue
        cy = AN.cyc_table(r, PT[pt]['Rmax'])
        be, C, first = AN.stop(r, cp, cy)
        n = min(len(be), len(bea))
        q = AN.boot_ratio(be[:n], bea[:n])
        q0 = AN.boot_ratio(r['biterr'][:n].astype(np.int64), ap['biterr'][:n].astype(np.int64))
        p0, x0, y0 = AN.mcnemar(be[:n], bea[:n])
        row = dict(c=cp, uses=n, antiphase=pk['method'], sa_err_uses=int((be[:n] > 0).sum()), ap_err_uses=int((bea[:n] > 0).sum()), ratio=q[0], lo=q[1], hi=q[2], mcnemar_p=p0, sa_only=x0, ap_only=y0,
                   nostop_ratio=q0[0], nostop_lo=q0[1], nostop_hi=q0[2], sa_nostop_err_uses=int((r['biterr'][:n] > 0).sum()), ap_nostop_err_uses=int((ap['biterr'][:n] > 0).sum()),
                   sa_cyc=float(C[:n].mean()), ap_cyc=float(Ca[:n].mean()), sa_p99=float(np.percentile(C[:n], 99)), ap_p99=float(np.percentile(Ca[:n], 99)), sa_max=float(C[:n].max()), ap_max=float(Ca[:n].max()),
                   sa_stop0=float((first[:n] == 0).mean()), sa_cyc_per_anneal=cy.tolist(), ap_cyc_per_anneal=cya.tolist(), by_c=[AN.stop_row(r, c1, cy) for c1 in AN.C_GRID])
        res.setdefault('sa_reinvest', {}).setdefault(pt, {})[m] = row
# (128, Ns) arms on the tuning seed: BER and cycles per stage count, and every c, for the trade between stages, anneals and the stop
for pt in ('P1', 'P2'):
    p = PT[pt]
    for st in ('A', 'B', 'N'):
        d = os.path.join(ROOT, st, p['sh'])
        if not os.path.isdir(d):
            continue
        for m in sorted(os.listdir(d)):
            if AN.sk_of(m) != 128 or m.split('_')[6] != 'alt' or float(m.split('_')[4]) != 0.4 or float(m.split('_')[2]) != 0.3 or float(m.split('_')[5]) != 0:
                continue
            r = run(st, pt, m)
            if r is None:
                continue
            res.setdefault('trade', {}).setdefault(pt, {})[m] = stop_section(r, pt, None)
# X3: production model against float on the same draws
for pt, m0 in (('P1', 'prod_fx_xs_32'), ('P2', 'prod_fx_xs_8')):
    p = PT[pt]
    fs = sorted(glob.glob(os.path.join(ROOT, 'X3P', p['sh'], m0, 'snr_%05.2f' % p['snr'], 'b*.npz')))
    if not fs or pt not in refs:
        continue
    prod = np.concatenate([np.load(f, allow_pickle=False)['biterr'] for f in fs]).astype(np.int64)
    fl = refs[pt]['biterr'].astype(np.int64)                               # refs already holds the X3F continuation
    n = min(len(prod), len(fl))
    q = AN.boot_ratio(prod[:n], fl[:n])
    mc = AN.mcnemar(prod[:n], fl[:n])
    res.setdefault('x3', {})[pt] = dict(uses=n, prod_err_uses=int((prod[:n] > 0).sum()), float_err_uses=int((fl[:n] > 0).sum()), prod_ber=float(prod[:n].sum()) / (n * p['bpu']),
                                        float_ber=float(fl[:n].sum()) / (n * p['bpu']), ratio=q[0], lo=q[1], hi=q[2], mcnemar_p=mc[0], prod_only=mc[1], float_only=mc[2])


# Amendment 5: Table IV's 64x64 row (seed 344, 22 dB, Ns 8): production model against float (i), and MMSE-SIC against both, same draws
def _contig(d):
    """biterr of the contiguous batches b00000, b00001, ... of one directory; stops at the first missing index."""
    out, bi = [], 0
    while os.path.exists(os.path.join(d, 'b%05d.npz' % bi)):
        out.append(np.load(os.path.join(d, 'b%05d.npz' % bi), allow_pickle=False)['biterr'])
        bi += 1
    return np.concatenate(out).astype(np.int64) if out else None


X64 = {k: _contig(os.path.join(ROOT, s, 'x64', m, 'snr_22.00')) for k, (s, m) in
       dict(prod=('X3P', 'prod_fx_xs_8'), float=('X64F', BASE('P2')), sic=('X64S', 'mmse_sic'),
            kb32=('X64K', 'kbest32'), kb64=('X64K', 'kbest64'), kb128=('X64K', 'kbest128')).items()}   # K-best: amendment 6, 6 Nov 2026
X64_PAIRS = dict(prod_float=('prod', 'float'), sic_prod=('sic', 'prod'), sic_float=('sic', 'float'))
for K in (32, 64, 128):
    X64_PAIRS['kb%d_prod' % K] = ('kb%d' % K, 'prod'); X64_PAIRS['kb%d_float' % K] = ('kb%d' % K, 'float')
for nm, (ka, kb) in X64_PAIRS.items():
    xa, xb = X64[ka], X64[kb]
    if xa is None or xb is None:
        continue
    n = min(len(xa), len(xb))
    q = AN.boot_ratio(xa[:n], xb[:n])
    mc = AN.mcnemar(xa[:n], xb[:n])
    res.setdefault('x64', {})[nm] = dict(uses=n, a=ka, b=kb, a_err_uses=int((xa[:n] > 0).sum()), b_err_uses=int((xb[:n] > 0).sum()),
                                         a_ber=float(xa[:n].sum()) / (n * 256), b_ber=float(xb[:n].sum()) / (n * 256), ratio=q[0], lo=q[1], hi=q[2],
                                         mcnemar_p=mc[0], a_only=mc[1], b_only=mc[2], passes_110=(q[2] is not None and q[2] <= 1.10) if nm == 'prod_float' else None)
tmp = os.path.join(ROOT, '.analysis.tmp')
json.dump(res, open(tmp, 'w'), indent=1)
os.rename(tmp, os.path.join(ROOT, 'analysis.json'))
