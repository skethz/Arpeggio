#!/usr/bin/env python3
"""A5.3d (PROTOCOL_A53.md Addendum 1, Sun 25 Oct 08:20 CET): x32 Ns 8 Table II with the old SA pick (abl_sa_8 = (ix),
2.4 -> 0.05), seed 101, the 10^-3 bracket only (18.5, 19.5, 20.5 dB), batch 1,000, frozen stopping rule; lowest priority.
Usage: make_plan_a53d.py OUT.json"""
import json, sys
J = [dict(set='tab2', shape='x32', method='abl_sa_8', snr=snr, seed=101, batch=1000, pri=0.1, a53=True, needs_tuned='sa')
     for snr in (20.5, 19.5, 18.5)]
json.dump(dict(host='hostB', amendment='A5.3d exploratory (lowest priority)',
               tuned_file='<SCRATCH>/ap_ber_20261024/results/tuned_a5.json', jobs=J), open(sys.argv[1], 'w'), indent=0)
print(len(J), 'jobs')
