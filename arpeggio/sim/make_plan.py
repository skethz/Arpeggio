#!/usr/bin/env python3
"""Builds the frozen job plans of PROTOCOL.md (one per host; every job lives in exactly one plan).
Usage: make_plan.py OUTDIR  ->  OUTDIR/plan_hosta.json, OUTDIR/plan_hostb.json, OUTDIR/grids.json"""
import json
import os
import sys

import numpy as np

OUT = sys.argv[1]
SEED_TAB2, SEED_ABL, SEED_MECH, SEED_TUNE, SEED_EQ = 101, 102, 104, 1000, 9100
BATCH = {'x16': 2000, 'x32': 1000, 'q16': 4000, 'q32': 4000}


def grid(lo, hi, step=0.5):
    return [round(float(x), 2) for x in np.arange(lo, hi + 1e-9, step)]


# Table II grids: 0.5 dB within +-2 dB of each old crossing (corrected rule, PROTOCOL.md 3.2); one-stage and MMSE-SIC
# rows whose old 1e-4 crossing lies beyond the old grid run to the old maximum SNR + 2 dB.
G = {
    ('x16', 'sic'): grid(22.5, 28.5) + [31.02],
    ('x16', 'kbest32'): grid(17.0, 22.5) + [31.02],
    ('x16', 'sd'): grid(16.0, 30.0),
    ('x16', 'aned64'): grid(21.0, 30.0),
    ('x16', 'mdiahck64'): grid(17.5, 26.0),
    ('x16', 'mdiane64'): grid(17.0, 23.5),
    ('x16', 'mdiahck8'): grid(19.5, 27.5),
    ('x16', 'mdiane8'): grid(19.0, 26.0),
    ('x16', 'mmse'): [31.02],
    ('x32', 'sic'): grid(23.0, 28.0),
    ('x32', 'kbest32'): grid(19.0, 24.5),
    ('x32', 'aned64'): grid(20.5, 28.0),
    ('x32', 'mdiahc128'): grid(18.0, 24.0),
    ('x32', 'mdiane128'): grid(16.5, 21.5),
    ('x32', 'mdiahc8'): grid(21.0, 26.5),
    ('x32', 'mdiane8'): grid(18.5, 24.5),
    ('q16', 'sic'): grid(11.0, 20.0),
    ('q16', 'kbest32'): grid(9.0, 14.5),
    ('q16', 'sd'): grid(8.5, 20.0),
    ('q16', 'ane64ri'): grid(10.0, 16.5),
    ('q16', 'mdiahck64'): grid(10.0, 16.0),
    ('q16', 'mdiane64'): grid(9.0, 14.5),
    ('q32', 'sic'): grid(11.0, 20.0),
    ('q32', 'kbest32'): grid(9.5, 14.5),
    ('q32', 'ane64ri'): grid(10.0, 16.5),
    ('q32', 'mdiahck64'): grid(11.0, 17.0),
    ('q32', 'mdiane64'): grid(8.5, 14.0),
}
# priority classes (lower first): 0 headline (published Ns, K-best, MMSE-SIC), 1 ML, 2 Ns = 8, 3 one-stage, 4 extra
PRI = {'mdiane64': 0, 'mdiane128': 0, 'mdiahck64': 0, 'mdiahc128': 0, 'kbest32': 0, 'sic': 0, 'sd': 1,
       'mdiane8': 2, 'mdiahck8': 2, 'mdiahc8': 2, 'aned64': 3, 'ane64ri': 3, 'mmse': 4}


def host_of(shape, method, st='tab2'):
    if method.startswith(('kbest', 'sd')):
        return 'hostA'                                                      # numba CPU on hostA (224 cores)
    if shape == 'x16' and method.startswith('mdiahck'):
        return 'hostA'                                                      # AHC kernel at K = 3 needs > 99 KB smem (B200 only)
    return 'hostB'


jobs = {'hostA': [], 'hostB': []}


def add(j, pri):
    j['pri'] = pri
    jobs[host_of(j['shape'], j['method'], j['set'])].append(j)


# ---- equivalence (both hosts; PROTOCOL.md 2)
for h in ('hostA', 'hostB'):
    for sh, m, snr, n in (('x16', 'mdiane64', 20.0, 8000), ('x16', 'sic', 22.0, 8000), ('q32', 'mdiane64', 12.0, 16000),
                          ('x32', 'mdiane8', 22.0, 2000), ('q32', 'mdiahck64', 12.0, 16000)):
        jobs[h].append(dict(set='equiv', shape=sh, method=m, snr=snr, seed=SEED_EQ, batch=BATCH[sh], min_vec=0, min_bit=0,
                            min_uses=n, max_bits=n * (64 if sh in ('x16', 'q32') else 128), pri=-10))

# ---- tuning of the three variants that have free settings (seed 1000, P1, n 4000; PROTOCOL.md 4.3)
TUNE = []
for c in (0.25, 0.5, 1.0, 2.0):
    for q0 in (0.0, 0.4):
        for T in (0.3, 0.6):
            TUNE.append('abl_qdimc_%g_%g_%g_32' % (c, q0, T))
for T0 in (0.3, 0.6, 1.2, 2.4):
    for T1 in (0.05, 0.15, T0):
        TUNE.append('abl_sat_%g_%g_32' % (T0, T1))
for T in (0.05, 0.1, 0.2, 0.4):
    for q in (0.0, 0.2, 0.4):
        TUNE.append('abl_symt_prop_%g_%g_32' % (T, q))
for T in (0.1, 0.2, 0.4, 0.8):
    for q in (0.4, 0.8, 1.6):
        TUNE.append('abl_symt_win_%g_%g_32' % (T, q))
for m in TUNE:
    add(dict(set='tune', shape='x16', method=m, snr=20.0, seed=SEED_TUNE, batch=2000, min_vec=0, min_bit=0, min_uses=4000,
             max_bits=4000 * 64), -5)

# ---- Table II (seed 101)
grids = {}
for (sh, m), g in G.items():
    grids['%s/%s' % (sh, m)] = g
    for snr in g:
        add(dict(set='tab2', shape=sh, method=m, snr=snr, seed=SEED_TAB2, batch=BATCH[sh]), PRI[m])

# ---- ablation (seed 102) at P1-P3
P = {'P1': ('x16', 20.0, 32, 8000, (32, 64)), 'P2': ('x32', 22.0, 8, 4000, (8, 32)), 'P3': ('q32', 14.0, 8, 8000, (8, 64))}
VAR = ['noalt', 'noaltq0', 'q0', 'qdim', 'dil', 'final', 'ons', 'pimi', 'sa', 'sym', 'symw']
NEEDS = {'qdim': 'qdim', 'sa': 'sa', 'sym': 'sym', 'symw': 'symw'}
for pt, (sh, snr, Ns, nmin, ahc_ns) in P.items():
    ms = ['mdiane%d' % Ns] + ['abl_%s_%d' % (v, Ns) for v in VAR] + ['mmse', 'kbest32'] + (['sic'] if sh != 'q32' else [])
    ms += [('mdiahck%d' if sh != 'x32' else 'mdiahc%d') % k for k in ahc_ns]
    for m in ms:
        j = dict(set='abl', shape=sh, method=m, snr=snr, seed=SEED_ABL, batch=BATCH[sh], min_uses=nmin, point=pt)
        v = m[4:].rsplit('_', 1)[0] if m.startswith('abl_') else None
        if v in NEEDS:
            j['needs_tuned'] = NEEDS[v]
        add(j, 0.5 if m.startswith('mdiane') or v in ('noalt', 'pimi', 'sym', 'qdim', 'final') else 1.5)

# ---- mechanism grid: BER against pinning q and temperature T, alternation on/off (seed 104, P1, n 4000)
for al in ('a', 's'):
    for q in (0.0, 0.1, 0.2, 0.4, 0.8, 1.6):
        for T in (0.1, 0.2, 0.3, 0.5, 0.8):
            add(dict(set='mech', shape='x16', method='abl_qt_%s_%g_%g_32' % (al, q, T), snr=20.0, seed=SEED_MECH,
                     batch=2000, min_vec=0, min_bit=0, min_uses=4000, max_bits=4000 * 64), 2.5)
for c in (0.25, 0.5, 1.0, 2.0, 4.0):
    add(dict(set='mech', shape='x16', method='abl_qdimc_%g_0_0.3_32' % c, snr=20.0, seed=SEED_MECH, batch=2000,
             min_vec=0, min_bit=0, min_uses=4000, max_bits=4000 * 64), 2.5)

# ---- fidelity ambiguity tests (seed 105; PROTOCOL.md 8): MDI-AHC kernel at 16x16 16-QAM 20 dB and 32x32 QPSK 13 dB
SEED_AMB = 105
for sh, snr, ms in (('x16', 20.0, ['mdiahck64', 'amb_om2_64', 'amb_x0sd_64', 'amb_floor_64', 'sic', 'sicc']),
                    ('x16', 24.0, ['sic', 'sicc']),
                    ('q32', 13.0, ['mdiahck64', 'amb_x0sd_64'])):
    for m in ms:
        j = dict(set='amb', shape=sh, method=m, snr=snr, seed=SEED_AMB, batch=BATCH[sh], min_uses=16000)
        j['pri'] = 3.5
        jobs['hostA' if (sh == 'x16' and (m.startswith('amb_') or m.startswith('mdiahck'))) else 'hostB'].append(j)

os.makedirs(OUT, exist_ok=True)
for h in jobs:
    js = sorted(jobs[h], key=lambda j: (j['pri'], j['set'], j['shape'], j['method'], j['snr']))
    plan = dict(host=h, tuned_file='<SCRATCH>/ap_ber_20261024/results/tuned.json', jobs=js)
    json.dump(plan, open(os.path.join(OUT, 'plan_%s.json' % h), 'w'), indent=0)
    print(h, len(js), 'jobs')
json.dump(grids, open(os.path.join(OUT, 'grids.json'), 'w'), indent=1)
