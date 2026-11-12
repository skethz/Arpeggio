#!/usr/bin/env python3
"""nvidia-smi cross-check of NVML energy, and GPU utilisation per segment: integrates the 100 ms power log
(power.draw.instant and power.draw, W; trapezoid over the samples inside each segment's [t_start, t_end], scaled to the
segment length) and compares with the NVML counter energy; averages utilization.gpu over the same samples (the time
the GPU is not busy is time the chain spends on the CPU side: Python orchestration and kernel launches).
Usage: smi_check.py BENCH.jsonl POWER_SMI.csv > smi_check.md"""
import csv
import datetime
import json
import sys

rows = [json.loads(l) for l in open(sys.argv[1])]
smp = []
for r in csv.reader(open(sys.argv[2])):
    try:
        ts = datetime.datetime.strptime(r[0].strip(), '%Y/%m/%d %H:%M:%S.%f').timestamp()
        smp.append((ts, float(r[1]), float(r[2]), float(r[3])))
    except (ValueError, IndexError):
        continue
smp.sort()
print('| Segment | NVML J | smi instant J | smi average J | instant / NVML | average / NVML | mean GPU utilisation % | samples |')
print('|---|---|---|---|---|---|---|---|')
ratios = []
for r in rows:
    if 't_start' not in r:
        continue
    pts = [s for s in smp if r['t_start'] <= s[0] <= r['t_end']]
    if len(pts) < 2:
        continue
    span = pts[-1][0] - pts[0][0]
    sc = (r['t_end'] - r['t_start']) / span
    ei = sc * sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(pts, pts[1:]))
    ea = sc * sum((b[0] - a[0]) * (a[2] + b[2]) / 2 for a, b in zip(pts, pts[1:]))
    ut = sum(p[3] for p in pts) / len(pts)
    ratios.append(ei / r['energy_J'])
    print('| %s %s %s | %.1f | %.1f | %.1f | %.3f | %.3f | %.0f | %d |' % (r['seg'], r.get('id', ''), r.get('rep', ''),
          r['energy_J'], ei, ea, ei / r['energy_J'], ea / r['energy_J'], ut, len(pts)))
if ratios:
    ratios.sort()
    print('\nsmi-instant / NVML over %d segments: median %.3f, range %.3f–%.3f' % (len(ratios), ratios[len(ratios) // 2],
                                                                               ratios[0], ratios[-1]))
