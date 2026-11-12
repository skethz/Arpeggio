#!/usr/bin/env python3
"""V80 many-small-instance engine: a resource and throughput ESTIMATE (design only; DESIGN.md B4), from the kernel's
measured per-instance work (flips per step and anneal, from the cohort's instrumented runs) and a stated cycle and
area model. Nothing here is synthesised.

Engine model (one MIMO instance at a time, its anneals one after another):
- N spin lanes; each holds its field u_i (24 bits), spin, and an RNG; a step issues the decisions of the active copy
  (N/P lanes) in one cycle; each flip then costs one cycle (one coupling row of N x 13 bits read and added to every
  field, as in the paper's flip-proportional engine), plus D_PIPE cycles of pipeline drain per step;
- best-state tracking: the energy is updated per flip from the flipped spin's field (one add), compared per step;
- couplings: N x N x 13 bits per instance, double-buffered (the next instance loads while this one anneals), in
  LUTRAM for N <= 32 and in BRAM otherwise (row width N x 13 bits over 72-bit BRAM ports);
- per lane LUT cost LUT_LANE (field adder, comparator with the threshold product, RNG, spin logic) and
  LUT_ENGINE of control per engine; clock F_MHZ.
Resources of the V80 (from the paper's utilisation table: 1,906,208 LUTs = 74.0 %, 3,318 BRAM = 88.7 %,
792 URAM = 41.1 %, 3,384 DSP58 = 31.2 %): about 2.58 M LUTs, 3,741 BRAM tiles, 1,927 URAM, 10,848 DSP58.
Usage: fpga_estimate.py COHORT.jsonl > estimate.md"""
import json
import math
import sys

F_MHZ = 300.0
D_PIPE = 2
LUT_LANE = 150
LUT_ENGINE = 1500
V80 = dict(LUT=2_576_000, BRAM=3_741, URAM=1_927, DSP=10_848)
BUDGET = 8.4e6                                                          # Princeton: 8,400 instances per 1 ms subframe
flips = [json.loads(l) for l in open(sys.argv[1]) if '"seg": "flips"' in l]
print('| Configuration | spins N | phases | steps S | anneals R | flips per step and anneal (measured) | cycles per detection '
      '| detections/s per engine | engines for 8.4 M/s | LUT | BRAM | fits the V80 |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|')
for r in flips:
    N, S, R, f, P = r['spins'], r['steps'], r['anneals'], r['flips_per_step_anneal'], r['phases']
    cyc = R * S * (1 + D_PIPE + f) + N                                    # + one cycle per coupling row to swap buffers
    per_engine = F_MHZ * 1e6 / cyc
    eng = math.ceil(BUDGET / per_engine)
    lut = eng * (N * LUT_LANE + LUT_ENGINE)
    bits = N * N * 13 * 2
    if N <= 32:
        lut += eng * math.ceil(bits / 64)                                  # LUTRAM, 64 bits per LUT
        bram = 0
    else:
        bram = eng * max(math.ceil(N * 13 / 72), math.ceil(bits / 36864))
    fits = lut <= 0.8 * V80['LUT'] and bram <= 0.9 * V80['BRAM']
    print('| %s | %d | %d | %d | %d | %.3f | %d | %.3g | %d | %.2f M (%.0f %%) | %d (%.0f %%) | %s |' %
          (r['name'], N, P, S, R, f, cyc, per_engine, eng, lut / 1e6, 100 * lut / V80['LUT'], bram,
           100 * bram / V80['BRAM'], 'yes' if fits else 'no'))
