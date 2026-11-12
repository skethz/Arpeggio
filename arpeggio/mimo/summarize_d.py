#!/usr/bin/env python3
"""Milestone-D cohort summary (markdown): medians over the 3 segments of every item; per point P1-P4 the PIMI and
Antiphase rows (same implementation: PyTorch both; best implementation: the faster of kernel and PyTorch each), the
ablation rows, the platform rows against the U55C's published numbers, and the check against PROTOCOL_D section 7
(ranges transcribed below as frozen; not revised). Usage: summarize_d.py COHORT_DIR PLAN_D.json > summary.md"""
import json
import statistics as st
import sys

d, plan = sys.argv[1], json.load(open(sys.argv[2]))
rows = [json.loads(l) for l in open(d + '/bench.jsonl')]
idle = [r for r in rows if r['seg'] == 'idle_noproc'][0]
by = {}
for r in rows:
    if r['seg'] in ('chain', 'solver'):
        by.setdefault(r['id'], []).append(r)
M = {}
for k, v in by.items():
    med = lambda f: st.median(x[f] for x in v)
    M[k] = {f: med(f) for f in ('ms_per_det', 'det_per_s', 'mJ_per_det', 'mJ_per_det_above_idle', 'avg_W', 'cpu_ms_per_det')}
    if v[0]['seg'] == 'chain':
        M[k].update({f: med(f) for f in ('solver_ms_per_det', 'rest_ms_per_det', 'ber')})
    M[k]['min_seg_s'] = min(x['seconds'] for x in v)
    M[k]['nseg'] = len(v)
items = {it['id']: it for it in plan['items']}
cheap = plan['cheapest']


def iid(p, meth, impl, x, mode='chain', v=''):
    return '%s_%s_%s_%s%s_%s' % (p, meth, impl, v, x, mode)


g = lambda x, n=3: '–' if x is None else ('%.*g' % (n, x))
print('# Milestone D cohort summary\n')
print('Idle (no process): %.1f W over %.0f s. Items: %d of %d measured; segments %.2f–%.2f s.\n' % (
    idle['avg_W'], idle['seconds'], len(M), len(items), min(x['seconds'] for v in by.values() for x in v),
    max(x['seconds'] for v in by.values() for x in v)))
STEPS = {'P1': (64, 256), 'P2': (128, 512), 'P3': (64, 256), 'P4': (64, 256)}
print('## Per point (chain, medians of 3 segments)\n')
print('| Point | method | implementation | setting | BER (timed) | ms/det | mJ/det total (above idle) | W | solver share |')
print('|---|---|---|---|---|---|---|---|---|')
for p in ('P1', 'P2', 'P3', 'P4'):
    c = cheap[p]
    lines = []
    for stp in STEPS[p]:
        for impl in ('torch', 'kernel'):
            lines.append(('PIMI' + (' (matched)' if stp == c['pimi_steps'] else ''), impl, '%d steps' % stp,
                          M.get(iid(p, 'pimi', impl, stp))))
    for impl in ('torch', 'kernel'):
        lines.append(('Antiphase (MDI)', impl, 'Ns %d' % c['ane_Ns'], M.get(iid(p, 'ane_mdi', impl, c['ane_Ns']))))
    if 'ane_ss_R' in c:
        for impl in ('torch', 'kernel'):
            lines.append(('Antiphase, one stage', impl, 'R %d' % c['ane_ss_R'], M.get(iid(p, 'ane_ss', impl, c['ane_ss_R']))))
    for name, impl, sett, m in lines:
        if m is None:
            continue
        print('| %s | %s | %s | %s | %s | %s | %s (%s) | %.0f | %.0f %% |' % (
            p, name, impl, sett, g(m['ber']), g(m['ms_per_det']), g(m['mJ_per_det']), g(m['mJ_per_det_above_idle']),
            m['avg_W'], 100 * m['solver_ms_per_det'] / m['ms_per_det']))
print('\n## Ratios Antiphase / PIMI per detection (> 1: PIMI cheaper; < 1: Antiphase cheaper)\n')
print('| Point | PIMI setting (matched?) | Antiphase | same implementation (PyTorch): time / energy | best implementation each: time / energy | BER PIMI / Antiphase (seed 42) |')
print('|---|---|---|---|---|---|')
for p in ('P1', 'P2', 'P3', 'P4'):
    c = cheap[p]
    for stp in STEPS[p]:
        for lab, meth, x in (('Antiphase (MDI) Ns %d' % c['ane_Ns'], 'ane_mdi', c['ane_Ns']),) + (
                (('Antiphase, one stage R %d' % c['ane_ss_R'], 'ane_ss', c['ane_ss_R']),) if 'ane_ss_R' in c else ()):
            pt, at = M.get(iid(p, 'pimi', 'torch', stp)), M.get(iid(p, meth, 'torch', x))
            pk, ak = M.get(iid(p, 'pimi', 'kernel', stp)), M.get(iid(p, meth, 'kernel', x))
            if not pt or not at:
                continue
            bp = min([m for m in (pt, pk) if m], key=lambda m: m['ms_per_det'])
            ba = min([m for m in (at, ak) if m], key=lambda m: m['ms_per_det'])
            matched = 'matched' if stp == c['pimi_steps'] and not c['pimi_never'] else ('never' if stp == c['pimi_steps'] else 'context')
            ber_a = c['ane_ber'] if meth == 'ane_mdi' else c['ane_ss_ber']
            print('| %s | %d steps (%s) | %s | %.3g / %.3g | %.3g / %.3g | %s / %s |' % (
                p, stp, matched, lab, at['ms_per_det'] / pt['ms_per_det'], at['mJ_per_det'] / pt['mJ_per_det'],
                ba['ms_per_det'] / bp['ms_per_det'], ba['mJ_per_det'] / bp['mJ_per_det'], g(c['pimi_ber'][str(stp)]), g(ber_a)))
print('\n## Ablation of Antiphase in MDI (variant i = the Antiphase item)\n')
print('| Point | implementation | variant | BER (timed) | ms/det | x (i) | mJ/det | x (i) |')
print('|---|---|---|---|---|---|---|---|')
for p in ('P1', 'P2', 'P3', 'P4'):
    ns = cheap[p]['ane_Ns']
    for impl in ('torch', 'kernel'):
        base = M.get(iid(p, 'ane_mdi', impl, ns))
        if not base:
            continue
        for v in ('i', 'ii', 'iii', 'iv'):
            m = base if v == 'i' else M.get(iid(p, 'abl', impl, ns, v=v))
            if m:
                print('| %s | %s | %s | %s | %s | %.2f | %s | %.2f |' % (p, impl, v, g(m['ber']), g(m['ms_per_det']),
                      m['ms_per_det'] / base['ms_per_det'], g(m['mJ_per_det']), m['mJ_per_det'] / base['mJ_per_det']))
print('\n## Platform rows (PIMI kernel alone and its chain, batch 10,000, Eb/N0 25 dB) against the U55C (published)\n')
U55 = {'16x16': dict(us=600.2, ms_100k=6169, kernels=10), '8x8': dict(us=146.8, ms_100k=1541, kernels=10)}
print('| Shape (16-QAM, steps) | B200 mode | us/det | detections/s | mJ/det total (above idle) | W | U55C (M, published): instances/s, us per instance per kernel | B200 / U55C throughput |')
print('|---|---|---|---|---|---|---|---|')
for sh, stp in (('16x16', 64), ('8x8', 32)):
    for mode in ('solver', 'chain'):
        m = M.get(iid('plat', 'pimi', 'kernel', stp, mode=mode))
        if not m:
            continue
        u = U55[sh]
        thr = 1e5 / (u['ms_100k'] * 1e-3)
        print('| %s (%d) | %s | %.3g | %.3g | %.3g (%.3g) | %.0f | %.3g, %.1f (%d kernels) | %.0f |' % (
            sh, stp, 'kernel alone' if mode == 'solver' else 'chain', 1e3 * m['ms_per_det'], m['det_per_s'],
            m['mJ_per_det'], m['mJ_per_det_above_idle'], m['avg_W'], thr, u['us'], u['kernels'], m['det_per_s'] / thr))
# ---------------------------------------------------------------- predictions check (PROTOCOL_D section 7, frozen)
PRED_MS = {  # (point, method, impl, setting) -> (lo, hi) ms per detection
    ('P1', 'pimi', 'torch', 64): (0.014, 0.038), ('P1', 'pimi', 'torch', 256): (0.052, 0.14),
    ('P1', 'pimi', 'kernel', 64): (0.0023, 0.0062), ('P1', 'pimi', 'kernel', 256): (0.0039, 0.0104),
    ('P2', 'pimi', 'torch', 128): (0.054, 0.145), ('P2', 'pimi', 'torch', 512): (0.20, 0.54),
    ('P2', 'pimi', 'kernel', 128): (0.0093, 0.025), ('P2', 'pimi', 'kernel', 512): (0.021, 0.055),
    ('P3', 'pimi', 'torch', 64): (0.013, 0.036), ('P3', 'pimi', 'torch', 256): (0.050, 0.135),
    ('P3', 'pimi', 'kernel', 64): (0.0034, 0.0092), ('P3', 'pimi', 'kernel', 256): (0.0069, 0.018),
    ('P4', 'pimi', 'torch', 64): (0.014, 0.038), ('P4', 'pimi', 'torch', 256): (0.052, 0.14),
    ('P4', 'pimi', 'kernel', 64): (0.0023, 0.0062), ('P4', 'pimi', 'kernel', 256): (0.0042, 0.0113),
    ('P1', 'ane_mdi', 'torch', None): (13, 34), ('P2', 'ane_mdi', 'torch', None): (35, 92),
    ('P3', 'ane_mdi', 'torch', None): (0.030, 0.080), ('P4', 'ane_mdi', 'torch', None): (1.7, 4.6),
    ('P1', 'ane_mdi', 'kernel', None): (0.17, 0.45), ('P3', 'ane_mdi', 'kernel', None): (0.0025, 0.0066),
    ('P4', 'ane_mdi', 'kernel', None): (0.036, 0.096),
    ('P4', 'ane_ss', 'torch', None): (0.08, 0.21), ('P4', 'ane_ss', 'kernel', None): (0.0021, 0.0058)}
PRED_US_PLAT = {'16x16': (0.55, 1.6), '8x8': (0.094, 0.37)}
print('\n## Against the frozen predictions (PROTOCOL_D section 7)\n')
nin = nout = 0
outs = []
for k, it in items.items():
    m = M.get(k)
    if not m:
        continue
    if it['point'] == 'plat':
        if it['mode'] == 'solver':
            lo, hi = PRED_US_PLAT[it['shape']]
            v = 1e3 * m['ms_per_det']
            ok = lo <= v <= hi; nin += ok; nout += not ok
            if not ok:
                outs.append('%s: %.3g us/det against %.3g–%.3g' % (k, v, lo, hi))
        continue
    key = (it['point'], it['method'], it['impl'], it.get('steps')) if it['method'] == 'pimi' else (it['point'], it['method'], it['impl'], None)
    if it['method'] == 'abl':
        continue
    if key in PRED_MS:
        lo, hi = PRED_MS[key]
        ok = lo <= m['ms_per_det'] <= hi; nin += ok; nout += not ok
        if not ok:
            outs.append('%s: %.3g ms/det against %.3g–%.3g' % (k, m['ms_per_det'], lo, hi))
print('Time ranges: %d inside, %d outside.\n' % (nin, nout))
for o in outs:
    print('- ' + o)
W = [m['avg_W'] for m in M.values()]
print('\nPower under load %.0f–%.0f W (predicted 250–950); idle %.1f W (180–220); shortest segment %.2f s (>= 6).' % (
    min(W), max(W), idle['avg_W'], min(m['min_seg_s'] for m in M.values())))
