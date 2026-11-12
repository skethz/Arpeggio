#!/usr/bin/env python3
"""Prediction table for PROTOCOL_C.md from the development pass only (bench_c.py on a shared GPU, one call per chain
item): per plan item the predicted ms per detection, range dev x [1/3, 1.5] (chain items: the chain time; solver-only
items: the in-chain solver time); where the development pass has no item with the same shape, SNR, method and
implementation at that Ns, the time is interpolated log-linearly in Ns between the nearest development Ns (or scaled
proportionally to Ns from the nearest one for the kernels, flat for PyTorch, whose time barely depends on Ns in the
development and BER runs, being launch-bound). Energy per detection: 250-950 W times the time range ends.
Usage: predict_c.py PLAN_C.json DEV.jsonl [DEV2.jsonl ...] > predictions_c.md"""
import json
import math
import sys

plan = json.load(open(sys.argv[1]))
dev = {}
for f in sys.argv[2:]:
    for l in open(f):
        r = json.loads(l)
        if r['seg'] != 'chain':
            continue
        k = (r['shape'], r['M'], r['snr'], r['method'], r['impl'])
        dev.setdefault(k, {})[r['Ns']] = (r['ms_per_det'], r['solver_ms_per_det'])


def est(it, which):
    d = dev.get((it['shape'], it['M'], it['snr'], it['method'], it['impl']))
    if not d:
        return None
    ns = it['Ns']
    if ns in d:
        return d[ns][which]
    lo = [n for n in d if n < ns]
    hi = [n for n in d if n > ns]
    if lo and hi:
        a, b = max(lo), min(hi)
        w = (math.log(ns) - math.log(a)) / (math.log(b) - math.log(a))
        return math.exp((1 - w) * math.log(d[a][which]) + w * math.log(d[b][which]))
    n0 = max(lo) if lo else min(hi)
    if it['impl'] == 'torch':                                             # PyTorch is launch-bound: flat in Ns
        return d[n0][which]
    return d[n0][which] * ns / n0


print('| Item | predicted ms per detection | predicted mJ per detection (total) |')
print('|---|---|---|')
for it in plan['items']:
    t = est(it, 0 if it['mode'] == 'chain' else 1)
    if t is None:
        print('| %s | – | – |' % it['id'])
        continue
    lo, hi = t / 3, t * 1.5
    print('| %s | %.3g–%.3g | %.3g–%.3g |' % (it['id'], lo, hi, 250 * lo, 950 * hi))         # W x ms = mJ
