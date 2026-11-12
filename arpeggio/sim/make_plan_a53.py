#!/usr/bin/env python3
"""A5.3 (exploratory; PROTOCOL_A53.md, coordinator's go Sun 25 Oct ~07:58 CET): (a) Table II x16 Ns 64 with the old SA
pick (abl_sa_64 = (ix), 2.4 -> 0.05), seed 101, 16.5-22.5 dB step 0.5, batch 2,000, the frozen stopping rule;
(b) P1 old-pick sweep series abl_sao_<S>_32, S = 1..64 (S = 128 is the existing abl_sa_32), seed 102, >= 8,000 uses.
Usage: make_plan_a53.py OUT.json"""
import json, sys
J = []
for i in range(12, -1, -1):                                            # runner takes jobs in plan order: longest (high SNR) first
    snr = 16.5 + 0.5 * i
    J.append(dict(set='tab2', shape='x16', method='abl_sa_64', snr=snr, seed=101, batch=2000, pri=1.0 + 0.01 * i, a53=True,
                  needs_tuned='sa'))
for S in (64, 32, 16, 8, 4, 2, 1):
    J.append(dict(set='abl', shape='x16', method='abl_sao_%d_32' % S, snr=20.0, seed=102, batch=2000, min_uses=8000, point='P1',
                  pri=0.5, a53=True, needs_tuned='sa'))
json.dump(dict(host='hostB', amendment='A5.3 exploratory', tuned_file='<SCRATCH>/ap_ber_20261024/results/tuned_a5.json',
               jobs=J), open(sys.argv[1], 'w'), indent=0)
print(len(J), 'jobs')
