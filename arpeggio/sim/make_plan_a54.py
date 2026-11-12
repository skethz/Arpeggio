#!/usr/bin/env python3
"""A5.4 (exploratory; PROTOCOL_A54.md): Antiphase schedule-length series at P1 and P2, seed 102. Cheapest jobs first; Sk 8192 last.
Usage: make_plan_a54.py OUT.json"""
import json, sys
J = []
for Sk in (32, 64, 128, 256, 512, 1024, 2048, 4096):
    J.append(dict(set='abl', shape='x16', method='abl_anel_%d_32' % Sk, snr=20.0, seed=102, batch=2000, min_uses=8000, point='P1', a54=True))
    J.append(dict(set='abl', shape='x32', method='abl_anel_%d_8' % Sk, snr=22.0, seed=102, batch=1000, min_uses=4000, point='P2', a54=True))
J.append(dict(set='abl', shape='x32', method='abl_anel_8192_8', snr=22.0, seed=102, batch=1000, min_uses=4000, point='P2', a54=True))
json.dump(dict(host='hostB', amendment='A5.4 exploratory', jobs=J), open(sys.argv[1], 'w'), indent=0)
print(len(J), 'jobs')
