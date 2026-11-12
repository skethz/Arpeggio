#!/usr/bin/env python3
"""Compact milestone-B scaling table for RESULTS.md from results/ber_scale_seed1/summary.json: SNR at BER 1e-3 of
MMSE, MMSE-SIC, the sphere decoder, K-best (K = 4, 32, 256), Anechoic (RI for QPSK; 1, 16, 256 anneals) and Anechoic
in the delta formulation (DI for QPSK, dDI for 16-QAM), the smallest K and anneal count within 0.2 dB of the best
1e-3 SNR, and the operating point. Usage: tables_b.py SUMMARY.json"""
import json
import sys

S = json.load(open(sys.argv[1]))


def f(c):
    if c is None:
        return '–'
    v, fl = c
    return {'ok': '%.1f' % v, 'ub': '≤%g' % v, 'below': '<%g' % v, 'above': '>%g' % v, 'none': '–'}[fl]


order = sorted(S, key=lambda k: (S[k]['M'], S[k]['rho'], -S[k]['nr'] / S[k]['nt'], S[k]['nt']))
print('| Configuration | MMSE | SIC | SD | K-best 4 / 32 / 256 | Anechoic RI 1 / 16 / 256 | Anechoic DI (QPSK) or dDI (16-QAM) 1 / 16 / 256 '
      '| smallest K / anneals within 0.2 dB | operating point: SNR, K*, R* |')
print('|---|---|---|---|---|---|---|---|---|')
for k in order:
    v = S[k]
    c = v['crossings']
    qp = v['M'] == 4
    ri = ' / '.join(f(c.get('ane%d' % R)) for R in (1, 16, 256)) if qp else '–'
    di = ' / '.join(f(c.get(('anedi%d' if qp else 'ane%d') % R)) for R in (1, 16, 256))
    kb = ' / '.join(f(c.get('kbest%d' % K)) for K in (4, 32, 256))
    sd = f(c.get('sd'))
    r02 = v.get('R_02_DI', v.get('R_02')) if qp else v.get('R_02')
    cx = '%s / %s' % (v.get('K_02') or '> 256', r02 or '> 256')
    op = ('%g dB, %d, %d' % (v['op_snr'], v['K'], v['R'])) if 'op_snr' in v else '–'
    name = '%d×%d %s%s' % (v['nt'], v['nr'], 'QPSK' if qp else '16-QAM', ', ρ 0.5' if v['rho'] else '')
    print('| %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (name, f(c.get('mmse')), f(c.get('sic')), sd, kb, ri, di, cx, op))
