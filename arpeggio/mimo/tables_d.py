#!/usr/bin/env python3
"""Milestone-D BER tables (markdown) from the result files: (1) the Fig. 6 validation (their report.json BER, our PIMI
on their instances, our PIMI on our port of their channel model, the figure reading); (2) the comparison at their
published operating points (held-out seed 41); (3) the matched-BER ladders and (4) the ablation (seed 42).
Usage: tables_d.py RESULTS_DIR REPORTS.jsonl > tables_d.md"""
import json
import math
import os
import re
import sys

rd, rep_path = sys.argv[1], sys.argv[2]
rep = {}
for l in open(rep_path):
    r = json.loads(l)
    m = re.search(r'Nt(\d+)_Nr\d+_(\d+)QAM/(\d+)/tanh_lut_4/16_precision/(\d+)_steps_32_anneals', r['path'])
    if m:
        rep[tuple(map(int, m.groups()))] = r['report']
DIRS = {(16, 4, 64): 128, (8, 64, 128): 256}
HW = {(8, 4): 16, (8, 16): 32, (8, 64): 64, (16, 4): 32, (16, 16): 64, (16, 64): 64}
TO = {(8, 4): 64, (8, 16): 128, (8, 64): 128, (16, 4): 64, (16, 16): 256, (16, 64): 256}   # steps the reports name
f = lambda x: '–' if x is None else ('0' if x == 0 else '%.2e' % x)

# ---------------------------------------------------------------- (1) validation
fig = [json.loads(l) for l in open(os.path.join(rd, 'pimi_fig6_d/fig6.jsonl'))]
rd_ = {(r['panel'], r['curve'], r['ebn0']): r for r in map(json.loads, open(os.path.join(rd, 'pimi_fig6_d/fig6_readings.jsonl')))}
PAN = {(8, 4): 'a', (8, 16): 'b', (8, 64): 'c', (16, 4): 'd', (16, 16): 'e', (16, 64): 'f'}
print('## Fig. 6 validation\n')
print('| Panel | Eb/N0 (dB) | curve (steps) | their report (exact) | figure reading | ours on their instances | ours on our port of their channel | their MMSE / ours |')
print('|---|---|---|---|---|---|---|---|')
z_all = {}
for (nt, M), p in PAN.items():
    for snr in sorted({k[2] for k in rep if k[:2] == (nt, M)}):
        for curve, st in (('HW', HW[(nt, M)]), ('TO', TO[(nt, M)])):
            t = rep.get((nt, M, snr, DIRS.get((nt, M, st), st)))
            if t is None:
                continue
            oi = [r for r in fig if r['source'] == 'their_instances' and (r['nt'], r['M'], r['ebn0'], r['steps']) == (nt, M, snr, st)]
            og = [r for r in fig if r['source'] == 'our_generator' and (r['nt'], r['M'], r['ebn0'], r['steps']) == (nt, M, snr, st)]
            rr = rd_.get((p, curve, snr))
            read = '%.2e [%.2e, %.2e]' % (rr['read'], rr['read_hi'], rr['read_lo']) if rr and rr.get('read') else '–'
            se = t['ber_std'] / math.sqrt(t['num_samples']) * math.sqrt(2)
            for src, v in (('i', oi), ('g', og)):
                if v and se > 0:
                    z_all.setdefault((nt, M, curve, src), []).append((v[0]['ber'] - t['ber']) / se)
            if t['ber'] < 1e-5 and (not oi or oi[0]['ber'] < 1e-5):
                continue
            print('| %s (%dx%d %d-QAM) | %d | %s (%d) | %s | %s | %s | %s | %s / %s |' % (
                p, nt, nt, M, snr, curve, st, f(t['ber']), read, f(oi[0]['ber']) if oi else '–', f(og[0]['ber']) if og else '–',
                f(t['ber_mmse']), f(og[0]['ber_mmse']) if og else '–'))
print('\nAgreement per panel, z = (ours - theirs) / (sqrt(2) x their per-instance std / sqrt(n)); rms z near 1 means run-to-run noise:\n')
print('| Panel | curve | on their instances: n, mean z, rms z | on our port of their channel: n, mean z, rms z |')
print('|---|---|---|---|')
for (nt, M), p in PAN.items():
    for curve in ('HW', 'TO'):
        cells = []
        for src in ('i', 'g'):
            v = z_all.get((nt, M, curve, src), [])
            cells.append('%d, %+.2f, %.2f' % (len(v), sum(v) / len(v), math.sqrt(sum(x * x for x in v) / len(v))) if v else '–')
        print('| %s (%dx%d %d-QAM) | %s | %s | %s |' % (p, nt, nt, M, curve, cells[0], cells[1]))
rr = [r for r in rd_.values() if r.get('read')]
offs = sorted(abs(r['offset_decades']) for r in rr)
print('\nFigure readings: %d markers read; |reading - report| median %.3f, max %.3f decades.\n' % (len(rr), offs[len(offs) // 2], offs[-1]))

# ---------------------------------------------------------------- (2)-(4) held-out BER
def load(name):
    p = os.path.join(rd, 'ber_d', name + '.jsonl')
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def tab(rows, cols, title):
    snrs = sorted({round(r['snr'], 2) for r in rows})
    have = [c for c in cols if any(r['method'] == c[0] for r in rows)]
    print('**%s**\n' % title)
    print('| Eb/N0 (dB) | SNR (dB) | ' + ' | '.join(c[1] for c in have) + ' |')
    print('|---|---|' + '---|' * len(have))
    for s in snrs:
        cells = []
        for m, _ in have:
            v = [r for r in rows if r['method'] == m and abs(r['snr'] - s) < 0.01]
            cells.append(f(v[0]['ber']) if v else '–')
        eb = [r['ebn0'] for r in rows if abs(r['snr'] - s) < 0.01][0]
        print('| %.1f | %.2f | %s |' % (eb, s, ' | '.join(cells)))
    print()


def cross(rows, m, target=1e-3):
    """Eb/N0 where BER crosses target (log-linear interpolation between grid points); None if never on the grid."""
    pts = sorted((r['ebn0'], r['ber']) for r in rows if r['method'] == m)
    if not pts:
        return None
    if pts[0][1] <= target:
        return '<=%.0f' % pts[0][0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y1 <= target < y0:
            if y1 <= 0:
                return '%.1f-%.0f' % (x0, x1)
            return '%.1f' % (x0 + (x1 - x0) * (math.log10(y0) - math.log10(target)) / (math.log10(y0) - math.log10(y1)))
    return '>%.0f' % pts[-1][0]


def crosstab(cfgs, cols):
    print('**Eb/N0 (dB) at BER 1e-3, log-linear interpolation on the grid (our SNR = Eb/N0 + 10 log10 b)**\n')
    print('| configuration | ' + ' | '.join(c[1] for c in cols) + ' |')
    print('|---|' + '---|' * len(cols))
    for name, rows in cfgs:
        print('| %s | %s |' % (name, ' | '.join((cross(rows, m) or '–') for m, _ in cols)))
    print()


C16 = [('mmse', 'MMSE (ours)'), ('mmseb', 'MMSE (theirs)'), ('kbest32', 'K-best 32'), ('pimi64', 'PIMI HW 64'),
       ('pimi256', 'PIMI TO 256'), ('pimi32', 'PIMI HW 32'), ('pimi128', 'PIMI TO 128'), ('aned32', 'Antiphase, 1 stage, 32'),
       ('aned64', 'Antiphase, 1 stage, 64'), ('mdiahc64', 'MDI-AHC Ns 64'), ('mdiane64', 'Antiphase Ns 64')]
print('## BER at their published operating points (held-out seed 41)\n')
tab(load('x16_a') + load('x16_ahc'), C16, '16x16 16-QAM (n 8,000; PIMI 64 / 256 steps)')
tab(load('x8_a'), C16, '8x8 16-QAM (n 16,000; PIMI 32 / 128 steps; our 16x16 schedules and Table I settings reused)')
CQ = [('mmse', 'MMSE'), ('kbest32', 'K-best 32'), ('pimi16', 'PIMI HW 16'), ('pimi32', 'PIMI HW 32'), ('pimi64', 'PIMI 64'),
      ('pimi128', 'PIMI TO 128'), ('pimiA16', 'PIMI-A HW 16'), ('pimiA32', 'PIMI-A HW 32'), ('pimiA64', 'PIMI-A 64'),
      ('pimiA128', 'PIMI-A 128'), ('aned32', 'Antiphase, 1 stage, 32'), ('aned64', 'Antiphase, 1 stage, 64'),
      ('mdiahc64', 'DI-AHC Ns 64'), ('mdiane64', 'Antiphase (DI) Ns 64')]
tab(load('q16_a'), CQ, '16x16 QPSK (n 16,000; PIMI 32 / 128 steps, and 64 as their report names; schedule B, PIMI-A = schedule A)')
tab(load('q8_a'), CQ, '8x8 QPSK (n 16,000; PIMI 16 / 64 steps)')
XC = [('mmse', 'MMSE (ours)'), ('mmseb', 'MMSE (theirs)'), ('kbest32', 'K-best 32'), ('pimiHW', 'PIMI HW'), ('pimiTO', 'PIMI TO'),
      ('pimiA_HW', 'PIMI-A HW'), ('aned32', 'Antiphase 1 stage 32'), ('aned64', 'Antiphase 1 stage 64'), ('mdiahc64', 'MDI-AHC / DI-AHC 64'),
      ('mdiane64', 'Antiphase 64')]


def alias(rows, hw, to, ahw=None):
    out = []
    for r in rows:
        r = dict(r)
        r['method'] = {'pimi%d' % hw: 'pimiHW', 'pimi%d' % to: 'pimiTO'}.get(r['method'], r['method'])
        if ahw and r['method'] == 'pimiA%d' % ahw:
            r['method'] = 'pimiA_HW'
        out.append(r)
    return out


crosstab([('16x16 16-QAM', alias(load('x16_a') + load('x16_ahc'), 64, 256)), ('8x8 16-QAM', alias(load('x8_a'), 32, 128)),
          ('16x16 QPSK', alias(load('q16_a'), 32, 128, 32)), ('8x8 QPSK', alias(load('q8_a'), 16, 64, 16))], XC)

print('## Matched-BER ladders and ablation (held-out seed 42)\n')
for p, title in (('P1_b', 'P1: 16x16 16-QAM, 20 dB (Eb/N0 13.98), n 8,000'), ('P2_b', 'P2: 32x32 16-QAM, 22 dB (Eb/N0 15.98), n 4,000'),
                 ('P3_b', 'P3: 32x32 QPSK, 14 dB (Eb/N0 10.99), n 8,000'), ('P4_b', 'P4: 16x16 16-QAM, 31.02 dB (Eb/N0 25), n 16,000')):
    rows = load(p)
    if not rows:
        continue
    print('**%s**\n' % title)
    print('| method | BER | mean anneals per detection |')
    print('|---|---|---|')
    for r in rows:
        print('| %s | %s | %s |' % (r['method'], f(r['ber']), ('%.1f' % r['mean_anneals']) if 'mean_anneals' in r else '–'))
    print()
