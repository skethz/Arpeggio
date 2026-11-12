#!/usr/bin/env python3
"""Milestone-B scaling tables. Per configuration: the SNR at BER 1e-3 of every detector setting (log-linear
interpolation between grid points, first crossing; '>x' not reached by the top of the grid, '<x' below it already),
and the operating point = the lowest grid SNR at which both a K-best K <= 256 and an Anechoic anneal count <= 256
reach BER <= 1e-3; there the smallest such K* and R*, with development wall times per detection (shared machine,
from the sweep; the timed cohort measures them properly) and SD node counts.
Usage: analyze_scale.py DIR [--json OUT.json] > tables.md"""
import glob
import json
import math
import os
import sys

TARGET = 1e-3


def crossing(pts, t=TARGET):
    pts = sorted(pts)
    if not pts:
        return None, 'none'
    if pts[0][1] < t:
        return pts[0][0], 'below'
    for (s0, b0), (s1, b1) in zip(pts, pts[1:]):
        if b0 >= t > b1:
            if b1 <= 0:
                return s1, 'ub'
            l0, l1, lt = math.log10(b0), math.log10(b1), math.log10(t)
            return s0 + (s1 - s0) * (l0 - lt) / (l0 - l1), 'ok'
    return pts[-1][0], 'above'


def fmt(c):
    v, f = c
    return {'ok': '%.1f' % v if v is not None else '–', 'ub': '≤%g' % v, 'below': '<%g' % v, 'above': '>%g' % v,
            'none': '–'}[f]


d = sys.argv[1]
summ = {}
order = []
for f in sorted(glob.glob(os.path.join(d, '*.jsonl'))):
    if f.endswith('_ddi.jsonl'):
        continue
    rows = [json.loads(l) for l in open(f)]
    fd = f[:-6] + '_ddi.jsonl'                    # QPSK delta-formulation ladder on the same draws: 'anediR'
    if os.path.exists(fd):
        main = {(r['method'], r['snr']): r for r in rows}
        for r in (json.loads(l) for l in open(fd)):
            if r['method'] in ('mmse', 'sic'):
                m0 = main.get((r['method'], r['snr']))
                assert m0 is None or m0['err'] == r['err'], 'draws differ: ' + fd
                continue
            r = dict(r, method='anedi' + r['method'][3:])
            rows.append(r)
    if not rows:
        continue
    r0 = rows[0]
    key = os.path.basename(f)[:-6]
    order.append(key)
    meth = []
    for r in rows:
        if r['method'] not in meth:
            meth.append(r['method'])
    t = {(r['method'], r['snr']): r for r in rows}
    snrs = sorted(set(r['snr'] for r in rows))
    cr = {m: crossing([(s, t[(m, s)]['ber']) for s in snrs if (m, s) in t]) for m in meth}
    ks = [m for m in meth if m.startswith('kbest')]
    an = [m for m in meth if m.startswith('ane') and not m.startswith('anedi')]
    di = [m for m in meth if m.startswith('anedi')]
    nR = lambda m: int(m[5:]) if m.startswith('anedi') else int(m[3:])
    op = None
    fam = di if di else an                        # QPSK: the delta-formulation ladder when present
    for s in snrs:
        kk = [m for m in ks if (m, s) in t and t[(m, s)]['ber'] <= TARGET]
        aa = [m for m in fam if (m, s) in t and t[(m, s)]['ber'] <= TARGET]
        if kk and aa:
            op = (s, min(kk, key=lambda m: int(m[5:])), min(aa, key=nR))
            break
    print('### %s: %d×%d %s, ρ = %g (%d channel uses per SNR, seed %d)\n' %
          (key, r0['nt'], r0['nr'], 'QPSK' if r0['M'] == 4 else '16-QAM', r0['rho'], r0['n'], r0['seed']))
    print('SNR at BER 1e-3 (dB):\n')
    print('| ' + ' | '.join(meth) + ' |')
    print('|' + '---|' * len(meth))
    print('| ' + ' | '.join(fmt(cr[m]) for m in meth) + ' |')
    if ('sd', snrs[0]) in t:
        print('\nSphere decoder: mean nodes per detection ' + ', '.join(
            '%g dB %.3g (%d unfinished)' % (s, t[('sd', s)]['mean_nodes'], t[('sd', s)]['sd_unfinished']) for s in snrs))
    S = dict(nt=r0['nt'], nr=r0['nr'], M=r0['M'], rho=r0['rho'], crossings={m: cr[m] for m in meth})
    ok_ = {m: cr[m][0] for m in meth if cr[m][1] in ('ok', 'ub')}
    if ok_:                                       # near-ML level: the best interpolated 1e-3 SNR of any detector
        ref = min(ok_.values())
        kn = [m for m in ks if m in ok_ and ok_[m] <= ref + 0.2]
        kmin = min(kn, key=lambda m: int(m[5:])) if kn else None
        S.update(best_snr=ref, K_02=int(kmin[5:]) if kmin else None)
        msg = 'smallest K %s' % (kmin[5:] if kmin else '> 256')
        for lab, fm in (('RI', an), ('DI', di)) if di else (('', an),):
            a_ = [m for m in fm if m in ok_ and ok_[m] <= ref + 0.2]
            amin = min(a_, key=nR) if a_ else None
            msg += ', smallest anneal count%s %s' % (' (' + lab + ')' if lab else '', nR(amin) if amin else '> 256')
            S['R_02' + ('_' + lab if lab else '')] = nR(amin) if amin else None
        print('\nWithin 0.2 dB of the best 1e-3 SNR (%.1f dB): %s.' % (ref, msg))
    if op:
        s, k, a = op
        per = lambda m: t[(m, s)]['seconds'] / t[(m, s)]['n']
        print('\nOperating point %g dB: K-best K* = %s (BER %.2e, dev %.2f µs/det on CPU), Anechoic%s R* = %s (BER %.2e, '
              'dev %.3f µs/det on GPU incl. mapping); MMSE %.2e, SIC %.2e.' %
              (s, k[5:], t[(k, s)]['ber'], 1e6 * per(k), '-DI' if di else '', nR(a), t[(a, s)]['ber'], 1e6 * per(a),
               t[('mmse', s)]['ber'], t[('sic', s)]['ber']))
        S.update(op_snr=s, K=int(k[5:]), R=nR(a), R_kind='ddi' if di or r0['M'] == 16 else 'ri', ber_K=t[(k, s)]['ber'], ber_R=t[(a, s)]['ber'],
                 dev_us_K=1e6 * per(k), dev_us_R=1e6 * per(a), mmse_ber=t[('mmse', s)]['ber'], sic_ber=t[('sic', s)]['ber'])
    else:
        print('\nNo grid SNR where both families reach BER 1e-3.')
    print()
    summ[key] = S
if '--json' in sys.argv:
    json.dump(summ, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
