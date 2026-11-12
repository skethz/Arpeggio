#!/usr/bin/env python3
"""Coded tables: BLER per (method, SNR), the SNR at BLER 0.1 and 0.01 (log-linear interpolation, first crossing) and
the gain over soft MMSE (positive = fewer dB). Usage: analyze_coded.py FILE.jsonl [FILE ...]"""
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
        return pts[-1][0], True
    if pts and pts[0][1] < target:
        return pts[0][0], 'below'
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
    print('### %s: %d×%d %d-QAM, LDPC k = %d, n = %d (rate %.2f), %d codewords per point, seed %d\n' %
          (f.split('/')[-1], r0['nt'], r0['nr'], r0['M'], r0['k'], r0['n'], r0['k'] / r0['n'], r0['codewords'], r0['seed']))
    print('| SNR (dB) | ' + ' | '.join(meths) + ' |')
    print('|---|' + '---|' * len(meths))
    for s in snrs:
        print('| %g | ' % s + ' | '.join(('%.4f' % t[(m, s)]['bler']) if (m, s) in t else '–' for m in meths) + ' |')
    print('\nCalibration factors α: ' + ', '.join('%s %.3f' % (m, t[(m, snrs[0])]['alpha']) for m in meths if (m, snrs[0]) in t))
    print('\n| Method | SNR at BLER 0.1 | SNR at BLER 0.01 | gain over soft MMSE at 0.1 / 0.01 (dB) |')
    print('|---|---|---|---|')
    cr = {m: {tg: crossing([(s, t[(m, s)]['bler']) for s in snrs if (m, s) in t], tg) for tg in (0.1, 0.01)} for m in meths}
    for m in meths:
        cells, gains = [], []
        for tg in (0.1, 0.01):
            v, flag = cr[m][tg]
            cells.append('–' if v is None else ('>%g' % v if flag is True else ('<%g' % v if flag == 'below' else '%.2f' % v)))
            vm, fm = cr['mmse'][tg] if 'mmse' in cr else (None, False)
            if v is None or vm is None or flag or fm:
                gains.append('–')
            else:
                gains.append('%.2f' % (vm - v))
        print('| %s | %s | %s | %s |' % (m, cells[0], cells[1], ' / '.join(gains)))
    print()
