#!/usr/bin/env python3
"""Compact milestone-C tables for RESULTS.md from the cohort (medians of 3 segments) and the held-out BER files.
Usage: tables_c.py COHORT_DIR PLAN_C.json"""
import json
import statistics as st
import sys

d, plan = sys.argv[1], json.load(open(sys.argv[2]))
rows = [json.loads(l) for l in open(d + '/bench.jsonl') if '"idle_noproc"' not in l]
by = {}
for r in rows:
    by.setdefault(r['id'], []).append(r)
med = {k: {f: st.median(x[f] for x in v) for f in v[0] if isinstance(v[0][f], (int, float)) and f not in ('rep',)}
       for k, v in by.items()}
BER = {}
for f in ('x16_a', 'x16_b_ahc', 'x16_b_ane', 'x32_a', 'x32_b_ahc', 'x32_b_ane', 'q32_a', 'q32_b', 'x64_c'):
    pt, key = f.split('_')[1], {'x16': '16x16', 'x32': '32x32', 'q32': '32x32q', 'x64': '64x64'}[f.split('_')[0]]
    for l in open('../results/ber_c/%s.jsonl' % f):
        r = json.loads(l)
        if r['method'].startswith('mdi'):
            BER[(pt, key, r['snr'], r['method'][3:6], int(r['method'][6:]))] = r['ber']
LAB = {'16x16': '16×16 16-QAM', '32x32': '32×32 16-QAM', '32x32q': '32×32 QPSK DI', '64x64': '64×64 16-QAM'}


def g(point, sh, snr, m, ns, impl, mode='chain'):
    return med.get('%s_%s_%g_%s%d_%s_%s' % (point, sh, snr, m, ns, impl, mode))


def fm(x):
    return '%.3g' % x


def bber(point, sh, snr, m, ns):
    b = BER.get((point, sh, snr, m, ns))
    return '–' if b is None else ('0' if b == 0 else '%.2e' % b)


def primary(points, title):
    print(title + '\n')
    print('| Configuration | SNR (dB) | Ns AHC / ours | BER AHC / ours | chain ms/det AHC / ours | of which solver | chain mJ/det AHC / ours (above idle) '
          '| solver-only mJ/det AHC / ours | time ratio | energy ratio |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for point, sh, snr, na, nn in points:
        a, b = g(point, sh, snr, 'ahc', na, 'torch'), g(point, sh, snr, 'ane', nn, 'torch')
        sa, sb = g(point, sh, snr, 'ahc', na, 'torch', 'solver'), g(point, sh, snr, 'ane', nn, 'torch', 'solver')
        print('| %s | %g | %d / %d | %s / %s | %s / %s | %.0f %% / %.0f %% | %s / %s (%s / %s) | %s / %s | **%.2f×** | **%.2f×** |' % (
            LAB[sh], snr, na, nn, bber(point, sh, snr, 'ahc', na), bber(point, sh, snr, 'ane', nn), fm(a['ms_per_det']), fm(b['ms_per_det']),
            100 * a['solver_ms_per_det'] / a['ms_per_det'], 100 * b['solver_ms_per_det'] / b['ms_per_det'],
            fm(a['mJ_per_det']), fm(b['mJ_per_det']), fm(a['mJ_per_det_above_idle']), fm(b['mJ_per_det_above_idle']),
            fm(sa['mJ_per_det']), fm(sb['mJ_per_det']), a['ms_per_det'] / b['ms_per_det'], a['mJ_per_det'] / b['mJ_per_det']))
    print()


def secondary(points, title):
    print(title + '\n')
    print('| Configuration | SNR (dB) | Ns AHC / ours | AHC kernel ms/det (mJ) | AHC PyTorch ms/det (mJ) | ours kernel ms/det (mJ) | of which solver '
          '| best AHC / best ours: time ratio | energy ratio |')
    print('|---|---|---|---|---|---|---|---|---|')
    for point, sh, snr, na, nn in points:
        ak, at, bk = g(point, sh, snr, 'ahc', na, 'kernel'), g(point, sh, snr, 'ahc', na, 'torch'), g(point, sh, snr, 'ane', nn, 'kernel')
        bt = g(point, sh, snr, 'ane', nn, 'torch')
        ba = min((ak, at), key=lambda x: x['ms_per_det'])
        bb = min((bk, bt), key=lambda x: x['ms_per_det'])
        print('| %s | %g | %d / %d | %s (%s) | %s (%s) | %s (%s) | %.0f %% | **%.1f×** (AHC %s) | **%.1f×** |' % (
            LAB[sh], snr, na, nn, fm(ak['ms_per_det']), fm(ak['mJ_per_det']), fm(at['ms_per_det']), fm(at['mJ_per_det']),
            fm(bk['ms_per_det']), fm(bk['mJ_per_det']), 100 * bk['solver_ms_per_det'] / bk['ms_per_det'],
            ba['ms_per_det'] / bb['ms_per_det'], 'kernel' if ba is ak else 'PyTorch', ba['mJ_per_det'] / bb['mJ_per_det']))
    print()


A = [('a', '16x16', s, 64, 64) for s in (18.0, 20.0, 22.0)] + [('a', '32x32', s, 128, 128) for s in (18.0, 20.0, 22.0)] + \
    [('a', '32x32q', s, 64, 64) for s in (10.0, 12.0)]
primary(A, '**(a) Published Ns, primary (both in PyTorch, same wrapper, batches and GPU)**')
secondary([p for p in A if p[1] != '32x32'], '**(a) Published Ns, secondary (each at its best implementation; kernels where the couplings fit in shared memory)**')
B = []
for sh, c in plan['cheapest'].items():
    B.append(('b', sh, c['snr'], c['ahc']['Ns'], c['ane']['Ns']))
primary(B, '**(b) Matched BER, primary: each method at its cheapest Ns reaching BER ≤ 10⁻³**')
secondary([p for p in B if p[1] != '32x32'], '**(b) Matched BER, secondary**')
E = []
for sh, c in plan['cheapest'].items():
    for ns in sorted({c['ahc']['Ns'], c['ane']['Ns']}):
        E.append(('b', sh, c['snr'], ns, ns))
primary(E, '**(b) Equal Ns at the matched-BER SNRs (context), primary**')
primary([('c', '64x64', 22.0, 8, 8)], '**(c) 64×64 16-QAM at 22 dB, Ns 8 (Princeton\'s massive-MIMO setting), primary**')
