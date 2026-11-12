#!/usr/bin/env python3
"""Milestone-E repeat cohort plans (PROTOCOL_E.md): the same configurations as the earlier matched-BER tables, new draws.
- PLAN_E_C.json: milestone C's matched-BER chain items (section 17 (b): 16x16 16-QAM 20 dB AHC Ns 64 / ours Ns 32,
  32x32 16-QAM 22 dB AHC Ns 32 / ours Ns 8, 32x32 QPSK 14 dB AHC Ns 64 / ours Ns 8; PyTorch and, where it exists, kernel),
  copied from PLAN_C.json with the draw seed set to SEED; run by src/bench_c.py.
- PLAN_E_D.json: milestone D's section-25 items (PIMI HW and 4x, Antiphase in MDI, Antiphase one stage; P1-P4), copied
  from PLAN_D.json (ablation and platform rows excluded) with the draw seed set to SEED; run by src/bench_d.py.
Usage: make_plan_e.py PLAN_C.json PLAN_D.json OUTDIR [SEED]"""
import json
import os
import sys

pc, pd, out = sys.argv[1], sys.argv[2], sys.argv[3]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 51_000_003
C_IDS = ['b_16x16_20_ahc64_torch_chain', 'b_16x16_20_ahc64_kernel_chain', 'b_16x16_20_ane32_torch_chain',
         'b_16x16_20_ane32_kernel_chain', 'b_32x32_22_ahc32_torch_chain', 'b_32x32_22_ane8_torch_chain',
         'b_32x32q_14_ahc64_torch_chain', 'b_32x32q_14_ahc64_kernel_chain', 'b_32x32q_14_ane8_torch_chain',
         'b_32x32q_14_ane8_kernel_chain']
c = {it['id']: it for it in json.load(open(pc))['items']}
items_c = [dict(c[i], seed=seed) for i in C_IDS]
d = json.load(open(pd))
items_d = [dict(it, seed=seed) for it in d['items'] if it['method'] in ('pimi', 'ane_mdi', 'ane_ss') and it['point'] != 'plat']
json.dump(dict(items=items_c, source='PLAN_C.json', seed=seed), open(os.path.join(out, 'PLAN_E_C.json'), 'w'), indent=1)
json.dump(dict(items=items_d, cheapest=d['cheapest'], source='PLAN_D.json', seed=seed),
          open(os.path.join(out, 'PLAN_E_D.json'), 'w'), indent=1)
print(len(items_c), 'C items;', len(items_d), 'D items')
