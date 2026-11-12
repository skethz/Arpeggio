#!/usr/bin/env python3
"""Milestone-C cohort summary: medians over the 3 segments of every item; tables for (a) published settings,
(b) matched BER and (c) 64x64, primary (PyTorch, both) and secondary (best implementation each: ours = the faster of
its kernel and PyTorch, theirs = the faster of its kernel and PyTorch), with the held-out BER of each configuration
(ber_c sweeps); the predictions check. Usage: summarize_c.py COHORT_DIR PLAN_C.json PREDICTIONS.md > summary.md"""
import json
import re
import statistics as st
import sys

d, plan = sys.argv[1], json.load(open(sys.argv[2]))
rows = [json.loads(l) for l in open(d + '/bench.jsonl')]
idle = [r for r in rows if r['seg'] == 'idle_noproc'][0]
by = {}
for r in rows:
    if r['seg'] in ('chain', 'solver'):
        by.setdefault(r['id'], []).append(r)
med = lambda v, k: st.median(x[k] for x in v)
M = {}
for k, v in by.items():
    M[k] = {f: med(v, f) for f in ('ms_per_det', 'mJ_per_det', 'mJ_per_det_above_idle', 'avg_W', 'cpu_ms_per_det', 'seconds')}
    if v[0]['seg'] == 'chain':
        M[k].update({f: med(v, f) for f in ('solver_ms_per_det', 'rest_ms_per_det', 'ber')})
    M[k]['min_seg_s'] = min(x['seconds'] for x in v)
# held-out BER of each configuration (PyTorch sweeps, fresh seeds)
BER = {}
for f, key in (('x16_a', '16x16'), ('x16_b_ahc', '16x16'), ('x16_b_ane', '16x16'), ('x32_a', '32x32'), ('x32_b_ahc', '32x32'),
               ('x32_b_ane', '32x32'), ('q32_a', '32x32q'), ('q32_b', '32x32q'), ('x64_c', '64x64')):
    pt = f.split('_')[1]                                                  # a, b or c: each point's own held-out seed
    for l in open('../results/ber_c/%s.jsonl' % f):
        r = json.loads(l)
        if r['method'].startswith('mdi'):
            BER[(pt, key, r['snr'], r['method'][3:6], int(r['method'][6:]))] = r['ber']


def iid(point, sh, snr, m, ns, impl, mode):
    return '%s_%s_%g_%s%d_%s_%s' % (point, sh, snr, m, ns, impl, mode)


def cell(point, sh, snr, m, ns, impl):
    c, s = M.get(iid(point, sh, snr, m, ns, impl, 'chain')), M.get(iid(point, sh, snr, m, ns, impl, 'solver'))
    return c, s


def best(point, sh, snr, m, ns):
    cand = [(impl,) + cell(point, sh, snr, m, ns, impl) for impl in ('torch', 'kernel')]
    cand = [c for c in cand if c[1]]
    if not cand:
        return None, None, None
    return min(cand, key=lambda c: c[1]['ms_per_det'])


def row(label, point, sh, snr, nsa, nsn, impls):
    out = []
    for impl in impls:
        if impl == 'best':
            ia, ca, sa = best(point, sh, snr, 'ahc', nsa)
            ib, cb, sb = best(point, sh, snr, 'ane', nsn)
            if not ca or not cb:
                continue
            lab = 'best (AHC: %s, Anechoic: %s)' % (ia, ib)
        else:
            ca, sa = cell(point, sh, snr, 'ahc', nsa, impl)
            cb, sb = cell(point, sh, snr, 'ane', nsn, impl)
            lab = impl
            if not ca or not cb:
                continue
        ba, bb = BER.get((point, sh, snr, 'ahc', nsa)), BER.get((point, sh, snr, 'ane', nsn))
        out.append('| %s | %g | %s | %d / %d | %s / %s | %.3g / %.3g | %.3g / %.3g | %.3g / %.3g | %.3g / %.3g (%.3g / %.3g) | %s | **%.2f×** | **%.2f×** |' % (
            label, snr, lab, nsa, nsn, '%.2e' % ba if ba is not None else '–', '%.2e' % bb if bb is not None else '–',
            ca['ms_per_det'], cb['ms_per_det'], ca['solver_ms_per_det'], cb['solver_ms_per_det'],
            ca['rest_ms_per_det'], cb['rest_ms_per_det'], ca['mJ_per_det'], cb['mJ_per_det'],
            ca['mJ_per_det_above_idle'], cb['mJ_per_det_above_idle'],
            ('%.3g / %.3g' % (sa['mJ_per_det'], sb['mJ_per_det'])) if sa and sb else '–',
            ca['ms_per_det'] / cb['ms_per_det'], ca['mJ_per_det'] / cb['mJ_per_det']))
    return out


HDR = ('| Configuration | SNR (dB) | implementation | Ns AHC / Anechoic | BER AHC / Anechoic | chain ms/det | in-chain solver ms/det '
       '| rest (MMSE, SIC, mapping, selection, orchestration) ms/det | chain mJ/det total (above idle) | solver-only mJ/det '
       '| AHC / Anechoic time | AHC / Anechoic energy |\n|---|---|---|---|---|---|---|---|---|---|---|---|')
print('Idle (no process): %.1f W over %.0f s.\n' % (idle['avg_W'], idle['seconds']))
print('### (a) Published settings (each pair: AHC / Anechoic)\n')
print(HDR)
for sh, snrs, ns, lab in (('16x16', (18.0, 20.0, 22.0), 64, '16×16 16-QAM'), ('32x32', (18.0, 20.0, 22.0), 128, '32×32 16-QAM'),
                          ('32x32q', (10.0, 12.0), 64, '32×32 QPSK DI')):
    for snr in snrs:
        for line in row(lab, 'a', sh, snr, ns, ns, ('torch', 'kernel', 'best') if sh in ('16x16', '32x32q') else ('torch',)):
            print(line)
print('\n### (b) Matched BER (cheapest Ns of each with BER ≤ 1e-3 on the seed-12 ladder; equal-budget rows below)\n')
print(HDR)
for sh, lab in (('16x16', '16×16 16-QAM'), ('32x32', '32×32 16-QAM'), ('32x32q', '32×32 QPSK DI')):
    c = plan['cheapest'].get(sh)
    if not c:
        continue
    na, nn = c['ahc']['Ns'], c['ane']['Ns']
    imp = ('torch', 'kernel', 'best') if sh in ('16x16', '32x32q') else ('torch',)
    for line in row(lab + ' (cheapest; AHC %s, Anechoic %s)' % ('meets' if c['ahc']['meets'] else 'NEVER meets',
                                                               'meets' if c['ane']['meets'] else 'NEVER meets'),
                    'b', sh, c['snr'], na, nn, imp):
        print(line)
    for ns in sorted({na, nn}):
        for line in row(lab + ' (equal Ns)', 'b', sh, c['snr'], ns, ns, imp):
            print(line)
print('\n### (c) 64×64 16-QAM, Ns 8 (Princeton\'s massive setting), PyTorch\n')
print(HDR)
for line in row('64×64 16-QAM', 'c', '64x64', 22.0, 8, 8, ('torch',)):
    print(line)
# predictions
pred = {}
for l in open(sys.argv[3]):
    m = re.match(r'\| (\S+) \| ([\d.e+-]+)–([\d.e+-]+) \| ([\d.e+-]+)–([\d.e+-]+) \|', l)
    if m:
        pred[m.group(1)] = tuple(float(m.group(i)) for i in range(2, 6))
out = []
for k, v in M.items():
    p = pred.get(k)
    if not p:
        out.append('%s: no prediction' % k)
        continue
    if not (p[0] <= v['ms_per_det'] <= p[1]):
        out.append('%s: time %.3g ms outside %.3g–%.3g' % (k, v['ms_per_det'], p[0], p[1]))
    if not (p[2] <= v['mJ_per_det'] <= p[3]):
        out.append('%s: energy %.3g mJ outside %.3g–%.3g' % (k, v['mJ_per_det'], p[2], p[3]))
segs = [x['seconds'] for x in rows if x['seg'] in ('chain', 'solver')]
print('\nSegments: %d, %.2f–%.1f s (all ≥ 6 s: %s). Items outside the predictions: %d of %d.' % (
    len(segs), min(segs), max(segs), all(s >= 6 for s in segs), len(out), len(M)))
for o in out:
    print('- ' + o)


# ---------------------------------------------------------------- verdict lines (ratios AHC / Anechoic)
def ratio(point, sh, snr, nsa, nsn, impl):
    if impl == 'best':
        ia, ca, sa = best(point, sh, snr, 'ahc', nsa)
        ib, cb, sb = best(point, sh, snr, 'ane', nsn)
    else:
        ca, sa = cell(point, sh, snr, 'ahc', nsa, impl)
        cb, sb = cell(point, sh, snr, 'ane', nsn, impl)
        ia = ib = impl
    if not ca or not cb:
        return None
    return dict(t=ca['ms_per_det'] / cb['ms_per_det'], e=ca['mJ_per_det'] / cb['mJ_per_det'],
                ea=ca['mJ_per_det_above_idle'] / cb['mJ_per_det_above_idle'], ta=ca['ms_per_det'], tb=cb['ms_per_det'],
                ja=ca['mJ_per_det'], jb=cb['mJ_per_det'], ia=ia, ib=ib,
                st=(sa['ms_per_det'] / sb['ms_per_det']) if sa and sb else None,
                se=(sa['mJ_per_det'] / sb['mJ_per_det']) if sa and sb else None)


print('\n### Verdict lines\n')
LAB = {'16x16': '16×16 16-QAM', '32x32': '32×32 16-QAM', '32x32q': '32×32 QPSK DI', '64x64': '64×64 16-QAM'}
pts = [('a', '16x16', s, 64, 64) for s in (18.0, 20.0, 22.0)] + [('a', '32x32', s, 128, 128) for s in (18.0, 20.0, 22.0)] + \
      [('a', '32x32q', s, 64, 64) for s in (10.0, 12.0)]
for sh, c in plan['cheapest'].items():
    pts.append(('b', sh, c['snr'], c['ahc']['Ns'], c['ane']['Ns']))
pts.append(('c', '64x64', 22.0, 8, 8))
for point, sh, snr, na, nn in pts:
    p = ratio(point, sh, snr, na, nn, 'torch')
    if p is None:
        print('- (%s) %s, %g dB: not measured' % (point, LAB[sh], snr))
        continue
    bst = ratio(point, sh, snr, na, nn, 'best') if sh in ('16x16', '32x32q') else None
    ba, bb = BER.get((point, sh, snr, 'ahc', na)), BER.get((point, sh, snr, 'ane', nn))
    s = '- (%s) %s, %g dB, Ns %d / %d (BER %.2e / %.2e): PyTorch both — ours %.1f× faster (%.3g vs %.3g ms), %.1f× less energy (%.3g vs %.3g mJ; above idle %.1f×), solver-only %.1f× time and %.1f× energy' % (
        point, LAB[sh], snr, na, nn, ba if ba is not None else float('nan'), bb if bb is not None else float('nan'),
        p['t'], p['ta'], p['tb'], p['e'], p['ja'], p['jb'], p['ea'], p['st'] or float('nan'), p['se'] or float('nan'))
    if bst:
        s += '; best implementations (AHC %s, ours %s) — %.1f× faster (%.3g vs %.3g ms), %.1f× less energy (%.3g vs %.3g mJ)' % (
            bst['ia'], bst['ib'], bst['t'], bst['ta'], bst['tb'], bst['e'], bst['ja'], bst['jb'])
    print(s + '.')
