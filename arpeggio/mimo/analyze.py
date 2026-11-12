#!/usr/bin/env python3
"""Tables from the BER sweeps: BER per (method, SNR); SNR at BER 1e-3 and 1e-4 by linear interpolation of log10 BER
between the bracketing SNR points (first crossing); gains over MMSE and over the CIM baselines at equal anneal
counts (positive = fewer dB). A target not reached inside the sweep is reported as '>max' and gains against it as
lower bounds. Usage: analyze.py FILE.jsonl [FILE ...] > tables.md"""
import json
import math
import sys


def crossing(pts, target):
    pts = sorted(pts)
    for (s0, b0), (s1, b1) in zip(pts, pts[1:]):
        if b0 >= target > b1:
            if b1 <= 0:
                return s1, False
            l0, l1, lt = math.log10(b0), math.log10(b1), math.log10(target)
            return s0 + (s1 - s0) * (l0 - lt) / (l0 - l1), False
    if pts and pts[-1][1] >= target:
        return pts[-1][0], True                                            # not reached: lower bound
    return None, False


for f in sys.argv[1:]:
    rows = [json.loads(l) for l in open(f)]
    meths = []
    for r in rows:
        if r['method'] not in meths:
            meths.append(r['method'])
    snrs = sorted(set(r['snr'] for r in rows))
    t = {(r['method'], r['snr']): r for r in rows}
    r0 = rows[0]
    print('### %s: %d×%d, %d-QAM, ρ = %g (%d channel uses per SNR, seed %d)\n' % (f.split('/')[-1], r0['nt'], r0['nr'], r0['M'], r0['rho'], r0['n'], r0['seed']))
    print('| SNR (dB) | ' + ' | '.join(meths) + ' |')
    print('|---|' + '---|' * len(meths))
    for s in snrs:
        print('| %g | ' % s + ' | '.join(('%.2e' % t[(m, s)]['ber']) if (m, s) in t else '–' for m in meths) + ' |')
    if ('sd', snrs[0]) in t:
        print('\nSphere decoder instances stopped by the node cap: ' + ', '.join('%g dB: %d' % (s, t[('sd', s)].get('sd_unfinished', 0)) for s in snrs if ('sd', s) in t))
    print('\n| Method | SNR at 1e-3 | SNR at 1e-4 | gain over MMSE at 1e-3 / 1e-4 (dB) |')
    print('|---|---|---|---|')
    cr = {}
    for m in meths:
        pts = [(s, t[(m, s)]['ber']) for s in snrs if (m, s) in t]
        cr[m] = {tg: crossing(pts, tg) for tg in (1e-3, 1e-4)}
    for m in meths:
        cells = []
        for tg in (1e-3, 1e-4):
            v, lb = cr[m][tg]
            cells.append('–' if v is None else ('>%g' % v if lb else '%.1f' % v))
        gains = []
        for tg in (1e-3, 1e-4):
            v, lb = cr[m][tg]
            vm, lbm = cr.get('mmse', {}).get(tg, (None, False))
            if v is None or vm is None or lb:
                gains.append('–')
            else:
                g = vm - v
                gains.append(('>%.1f' if lbm else '%.1f') % g)
        print('| %s | %s | %s | %s |' % (m, cells[0], cells[1], ' / '.join(gains)))
    print()
