#!/usr/bin/env python3
"""Our BER evaluation on the authors' own solved states (DI_MIMO_sol_k of their Fig. 6 settings, from the Zenodo
archives) must reproduce their report.json values (ber, ber_mmse) — a check of our bit mapping, reconstruction
(x_mmse + T s, nearest point) and averaging, independent of any solver. Usage: check_pimi_reports.py CACHE REPORTS.jsonl OUT.jsonl"""
import glob
import json
import os
import re
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pimi  # noqa: E402

cache, rep, out = sys.argv[1], sys.argv[2], sys.argv[3]
reports = {}
for line in open(rep):
    r = json.loads(line)
    m = re.search(r'Nt(\d+)_Nr\d+_(\d+)QAM/(\d+)/([^/]+)/(\d+)_precision/(\d+_steps_\d+_anneals)', r['path'])
    nt, M, snr, alg, prec, sub = m.groups()
    reports[(int(nt), int(M), int(snr), alg, int(prec), sub)] = r['report']
fo = open(out, 'w')
nok = nbad = 0
for f in sorted(glob.glob(os.path.join(cache, 'nt*_M*_snr*.npz'))):
    nt, M, snr = map(int, re.search(r'nt(\d+)_M(\d+)_snr(\d+)', f).groups())
    z = np.load(f)
    xt, xm = torch.tensor(z['xt'], dtype=torch.float32), torch.tensor(z['xm'], dtype=torch.float32)
    em, nbits = pimi.bit_errors(xt, xm, M)
    for key in z.files:
        if not key.startswith('sol_'):
            continue
        sub = key[4:]
        s = torch.tensor(z[key], dtype=torch.float32)
        D = 2 * nt
        lh = pimi.slice_levels(xm + s[:, :D] + s[:, D:], M)
        e, _ = pimi.bit_errors(xt, lh, M)
        r = reports.get((nt, M, snr, 'tanh_lut_4', 16, sub))
        ber, berm = e / nbits, em / nbits
        same = r is not None and abs(ber - r['ber']) < 1e-12 and abs(berm - r['ber_mmse']) < 1e-12
        nok += same; nbad += not same
        rec = dict(nt=nt, M=M, ebn0=snr, setting=sub, n=int(xt.shape[0]), ber_ours=ber, ber_mmse_ours=berm,
                   ber_report=None if r is None else r['ber'], ber_mmse_report=None if r is None else r['ber_mmse'],
                   report_num_steps=None if r is None else r['num_steps'], zero_spins=int((s == 0).sum()), match=same)
        fo.write(json.dumps(rec) + '\n')
        if not same:
            print('MISMATCH', rec, flush=True)
print('reports reproduced exactly: %d, mismatches: %d' % (nok, nbad), flush=True)
sys.exit(0 if nbad == 0 else 1)
