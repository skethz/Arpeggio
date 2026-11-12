#!/usr/bin/env python3
"""Summary of the milestone-B timed cohort: per item the median over its segments of detections/s, µs per detection,
power and J per detection (total and above the no-process idle), BER, load average; the frozen predictions next to
it and whether the result lies inside them. Writes markdown tables (kernel items; scaling cost table GPU vs CPU)
and the flips records. Usage: summarize_b.py COHORT_DIR PREDICTIONS.md > summary.md"""
import json
import re
import statistics as st
import sys

d = sys.argv[1]
rows = [json.loads(l) for l in open(d + '/bench.jsonl')]
pred = {}
for l in open(sys.argv[2]):
    m = re.match(r'\| (\S+ \S+(?: R\d+)?) \| ([\d.e+-]+)–([\d.e+-]+) \| ([\d.e+-]+)–([\d.e+-]+) \|', l)
    if m:
        pred[m.group(1)] = tuple(float(m.group(i)) for i in range(2, 6))
    m = re.match(r'\| (scale_\S+) \| (\d+) \| ([\d.e+-]+)–([\d.e+-]+) \|', l)
    if m:
        pred['cpu ' + m.group(1)] = (float(m.group(3)), float(m.group(4)))
idle = [r for r in rows if r['seg'] == 'idle_noproc'][0]
print('Idle (no process): %.1f W over %.0f s.\n' % (idle['avg_W'], idle['seconds']))
g = {}
for r in rows:
    if r['seg'].startswith('gpu_') or r['seg'] == 'cpu_kbest':
        key = (r['seg'], r['name'], r.get('mode'), r.get('anneals'), r.get('K'))
        g.setdefault(key, []).append(r)
md = lambda v, k: st.median(x[k] for x in v) if all(x.get(k) is not None for x in v) else None
print('| Item | mode | anneals | detections/s (M) | µs/det | W | J/det total (mJ) | above idle (mJ) | BER | predicted M det/s | predicted mJ | inside |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|')
for (seg, name, mode, R, K), v in g.items():
    if seg == 'cpu_kbest' or name.startswith('scale_'):
        continue
    tag = '%s %s%s' % (name, mode, (' R%d' % R) if R else '')
    rate = md(v, 'det_per_s') / 1e6
    jt = md(v, 'J_per_det') * 1e3
    p = pred.get(tag)
    inside = '–' if p is None else ('yes' if (p[0] <= rate <= p[1] and p[2] <= jt <= p[3]) else
                                   'rate %s, energy %s' % ('in' if p[0] <= rate <= p[1] else 'OUT', 'in' if p[2] <= jt <= p[3] else 'OUT'))
    print('| %s | %s | %s | %.3g | %.4g | %.0f | %.3g | %.3g | %s | %s | %s | %s |' % (
        name, mode, R or '–', rate, md(v, 'us_per_det'), md(v, 'avg_W'), jt, md(v, 'J_per_det_above_idle') * 1e3,
        '%.2e' % md(v, 'ber') if md(v, 'ber') is not None else '–', '%.3g–%.3g' % p[:2] if p else '–',
        '%.3g–%.3g' % p[2:] if p else '–', inside))
print('\n| Configuration | SNR | K* | K-best CPU µs/det (BER) | load avg | predicted µs | R* | Anechoic GPU µs/det (BER) | J/det GPU (mJ) | predicted M det/s | CPU/GPU time ratio |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
cpu = {k[1]: v for k, v in g.items() if k[0] == 'cpu_kbest'}
gpu = {k[1]: v for k, v in g.items() if k[0] == 'gpu_e2e' and k[1].startswith('scale_')}
for name in cpu:
    c, gg = cpu[name], gpu.get(name)
    pc = pred.get('cpu ' + name)
    pg = pred.get('%s e2e R%d' % (name, gg[0]['anneals'])) if gg else None
    cu, gu = md(c, 'us_per_det'), md(gg, 'us_per_det') if gg else None
    print('| %s | %g | %d | %.3g (%.1e) | %.0f | %s | %s | %s | %s | %s | %s |' % (
        name[len('scale_'):], c[0]['snr'], c[0]['K'], cu, md(c, 'ber'), md(c, 'loadavg_start'),
        ('%.3g–%.3g %s' % (pc[0], pc[1], 'in' if pc[0] <= cu <= pc[1] else 'OUT')) if pc else '–',
        gg[0]['anneals'] if gg else '–', ('%.3g (%.1e)' % (gu, md(gg, 'ber'))) if gg else '–',
        '%.3g' % (md(gg, 'J_per_det') * 1e3) if gg else '–',
        ('%.3g–%.3g %s' % (pg[0], pg[1], 'in' if pg[0] <= 1 / gu <= pg[1] else 'OUT')) if pg and gu else '–',
        '%.1f' % (cu / gu) if gu else '–'))
print()
for r in rows:
    if r['seg'] == 'flips':
        print('flips %s: %d spins, %d phases, S %d, R %d: %.3f flips per step and anneal, %.3f energy updates per step, '
              '%.0f flips, %.0f decisions and %.0f field MACs per detection' % (
                  r['name'], r['spins'], r['phases'], r['steps'], r['anneals'], r['flips_per_step_anneal'],
                  r['energy_updates_per_step'], r['flips_per_detection'], r['decisions_per_detection'],
                  r['field_macs_per_detection']))
