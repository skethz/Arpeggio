#!/usr/bin/env python3
"""V80 many-small-instance engine: a resource and throughput ESTIMATE (design only; DESIGN.md B4), from the kernel's
measured per-instance work (flips per step and anneal, the cohort's instrumented runs) and a stated cycle and area
model. Nothing here is synthesised. (v1, fpga_estimate_v1.py, charged 2 drain cycles per step and 150 LUTs per lane;
this version interleaves 3 anneals per engine so the drain is hidden, and uses the paper's measured logic density.)

Engine model: one MIMO instance at a time; N spin lanes, each holding the spin, three field registers (three anneals
interleaved round-robin, which hides the 2-cycle pipeline drain of a step) and a 32-bit RNG; a step issues the
decisions of the active copy (N/P lanes) in one cycle and then one cycle per flipped spin (one coupling row of
N x 13 bits added to every field, the paper's flip-proportional rule); best-state tracking by a per-flip energy add.
Cycles per detection = R * S * (1 + f) + N (coupling load), f = measured flips per step and anneal.
Area: LUT_LANE LUTs per lane (the paper's v6 engine uses 149,512 LUTs for 2,000 spins, about 75 per spin; +25 for the
two extra field registers), LUT_ENGINE per engine; couplings double-buffered, N x N x 13 bits x 2: LUTRAM (one LUT per
read bit, depth 64) for N <= 32, else BRAM36 (72-bit ports; ceil(N x 13 / 72) tiles hold both buffers when 2N <= 512).
V80: about 2.58 M LUTs, 3,741 BRAM36, 10,848 DSP58 (from the paper's utilisation table). Clock F_MHZ.
Usage: fpga_estimate.py COHORT.jsonl > estimate.md"""
import json
import math
import sys

F_MHZ = 300.0
LUT_LANE = 100
LUT_ENGINE = 2000
V80 = dict(LUT=2_576_000, BRAM=3_741)
BUDGET = 8.4e6
flips = [json.loads(l) for l in open(sys.argv[1]) if '"seg": "flips"' in l]
seen = set()
print('| Configuration | spins N | phases | S | anneals R | flips per step and anneal (measured) | cycles per detection '
      '| detections/s per engine | engines for 8.4 M/s | LUT | BRAM36 | fits (≤ 80 % LUT, ≤ 90 % BRAM) |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|')
for r in flips:
    for R in sorted({4, r['anneals']}):
        key = (r['name'], R)
        if key in seen:
            continue
        seen.add(key)
        N, S, f, P = r['spins'], r['steps'], r['flips_per_step_anneal'], r['phases']
        cyc = R * S * (1 + f) + N
        per_engine = F_MHZ * 1e6 / cyc
        eng = math.ceil(BUDGET / per_engine)
        lut = eng * (N * LUT_LANE + LUT_ENGINE)
        if N <= 32:
            lut += eng * N * 13                                           # LUTRAM read width, depth 64 = 2 buffers
            bram = 0
        else:
            bram = eng * math.ceil(N * 13 / 72)
        fits = lut <= 0.8 * V80['LUT'] and bram <= 0.9 * V80['BRAM']
        print('| %s | %d | %d | %d | %d | %.3f | %d | %.3g | %d | %.2f M (%.0f %%) | %d (%.0f %%) | %s |' %
              (r['name'], N, P, S, R, f, cyc, per_engine, eng, lut / 1e6, 100 * lut / V80['LUT'], bram,
               100 * bram / V80['BRAM'], 'yes' if fits else 'no'))
