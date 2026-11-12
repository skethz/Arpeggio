#!/usr/bin/env python3
"""Amendment A5 (+A5.1 refinements folded in before freezing) plan, PROTOCOL_A5.md. hostB GPU0 only.
Tier 1 = everything except the 0.5-dB fill of the x32 SA Table II curve (tier 2, lowest priority).
Usage: make_plan_a5.py OUT.json"""
import json, sys
import numpy as np


def grid(lo, hi, st=0.5):
    return [round(float(x), 2) for x in np.arange(lo, hi + 1e-9, st)]


J = []
PT = {'P1': ('x16', 20.0, 32, 8000, 2000, 4000), 'P2': ('x32', 22.0, 8, 4000, 1000, 2000), 'P3': ('q32', 14.0, 8, 8000, 4000, 4000)}


def tune(sh, m, n, b, pri, **kw):
    bpu = 64 if sh in ('x16', 'q32') else 128
    J.append(dict(set='tune', shape=sh, method=m, snr=PT[{'x16': 'P1', 'x32': 'P2', 'q32': 'P3'}[sh]][1], seed=1000, batch=b,
                  min_vec=0, min_bit=0, min_uses=n, max_bits=n * bpu, pri=pri, a5=True, **kw))


def held(pt, m, pri, st='abl', **kw):
    sh, snr, Ns, nmin, B, _ = PT[pt]
    J.append(dict(set=st, shape=sh, method=m, snr=snr, seed=102 if st == 'abl' else 104, batch=B, min_uses=nmin, point=pt, pri=pri, a5=True, **kw))


# ---- tuning (seed 1000)
for pt, (sh, snr, Ns, nmin, B, nt) in PT.items():
    for bud in ('cyc', 'fl'):                                              # A5d parallel trial: 12 cells per budget and point
        for T0 in (0.3, 0.6, 1.2, 2.4):
            for T1 in (0.05, 0.15, T0):
                tune(sh, 'abl_ptt_%s_%g_%g_%d' % (bud, T0, T1, Ns), nt, B, -5, needs_tuned='flip_phi')
    for c in (0.5, 1, 2, 4):                                              # (iv) re-tuned per point (C2 control)
        for T in (0.3, 0.6, 1.2, 2.4):
            tune(sh, 'abl_qdimc_%g_0.4_%g_%d' % (c, T, Ns), nt, B, -5)
for T0 in (0.3, 0.6, 1.2, 2.4):                                           # A5a SA: original 12 cells (done) + extension
    for T1 in (0.05, 0.15, T0):
        tune('x16', 'abl_sat_%g_%g_32' % (T0, T1), 4000, 2000, -5)
for T0 in (2.4, 4.8, 9.6):
    for T1 in (0.0125, 0.025, 0.05):
        tune('x16', 'abl_sat_%g_%g_32' % (T0, T1), 4000, 2000, -5)
for q in (0.2, 0.4, 0.8):                                                 # b1: P colours by dimension, copies in phase
    for T in (0.1, 0.2, 0.3, 0.5):
        tune('x16', 'abl_dimt_%g_%g_32' % (q, T), 4000, 2000, -5)
for T in (0.05, 0.1, 0.2, 0.4):                                           # b2: (x) diluted to 1/P
    for q in (0.0, 0.2, 0.4):
        tune('x16', 'abl_symdt_%g_%g_32' % (T, q), 4000, 2000, -5)
for sh, Ns, ms, n, B in (('x16', 32, (16, 8, 4, 2, 1, 0), 4000, 2000), ('x32', 8, (32, 16, 8, 4, 2, 1, 0), 2000, 1000)):
    for m in ms:                                                          # A5b per-c (q, T), 12 cells, at each point
        for q in (0.2, 0.4, 0.8):
            for T in (0.1, 0.2, 0.3, 0.5):
                tune(sh, 'abl_colt_%d_%g_%g_%d' % (m, q, T, Ns), n, B, -4.5 + 0.01 * (32 - m))
# ---- held-out (seed 102; mech grid seed 104)
for pt in ('P1', 'P2', 'P3'):
    Ns = PT[pt][2]
    held(pt, 'abl_ptc_%d' % Ns, 0, needs_tuned='pt_cyc')                  # kill-rule arm (P1-tuned, same privilege)
    held(pt, 'abl_ptf_%d' % Ns, 0, needs_tuned='pt_fl')
    if pt != 'P1':
        held(pt, 'abl_ptcp_%d' % Ns, 0.1, needs_tuned='pt_cyc_' + PT[pt][0])   # sensitivity: tuned at this point
        held(pt, 'abl_ptfp_%d' % Ns, 0.1, needs_tuned='pt_fl_' + PT[pt][0])
    held(pt, 'abl_qdimk_%d' % Ns, 1.0, needs_tuned='qdim_pp')
for pt in ('P1', 'P2'):
    Ns = PT[pt][2]
    for S in (128, 64, 32, 16, 8, 4, 2, 1):                               # A5a sweep-count series
        held(pt, 'abl_sas_%d_%d' % (S, Ns), 0.5 if (pt == 'P2' and S >= 64) else 1.0, needs_tuned='sa2')
    for m in ((16, 8, 4, 2, 1, 0) if pt == 'P1' else (32, 16, 8, 4, 2, 1, 0)):
        held(pt, 'abl_colk_%d_%d' % (m, Ns), 0.5 if (pt == 'P2' and m >= 16) else 1.0, needs_tuned='col_' + PT[pt][0])
    held(pt, 'abl_dimk_%d' % Ns, 1.0, needs_tuned='dim')
    held(pt, 'abl_symdk_%d' % Ns, 1.0, needs_tuned='symd')
for m in (16, 8, 4, 2, 0):                                                # A5b frozen (q 0.4, T 0.3) curve at P1 (m = 1 is (i))
    held('P1', 'abl_col_%d_32' % m, 1.5)
for q in (1.6, 3.2, 6.4):                                                 # C2: alternation-off grid extension (seed 104)
    for T in (0.8, 1.6, 3.2):
        J.append(dict(set='mech', shape='x16', method='abl_qt_s_%g_%g_32' % (q, T), snr=20.0, seed=104, batch=2000, min_vec=0,
                      min_bit=0, min_uses=4000, max_bits=4000 * 64, pri=1.0, a5=True))
# ---- A5a Table II conversion (seed 101): x16 published Ns 64 (0.5 dB); x32 Ns 8 (1-dB tier 1, 0.5-dB fill tier 2)
for snr in grid(16.5, 22.5):
    J.append(dict(set='tab2', shape='x16', method='abl_sa2_64', snr=snr, seed=101, batch=2000, pri=0.8, a5=True, needs_tuned='sa2'))
for snr in grid(18.5, 24.5):
    tier2 = (round(snr * 2) % 2) == 0                                     # x.0 points are the tier-2 fill
    J.append(dict(set='tab2', shape='x32', method='abl_sa2_8', snr=snr, seed=101, batch=1000, pri=5.0 if tier2 else 0.6,
                  tier=2 if tier2 else 1, a5=True, needs_tuned='sa2'))
# ---- optional, CPU only: K-best K-sweep at the Table II points (seed 101)
for sh, g in (('x16', grid(16.5, 24.0)), ('x32', grid(18.0, 26.0))):
    for K in (8, 16, 64, 128):
        for snr in g:
            J.append(dict(set='tab2', shape=sh, method='kbest%d' % K, snr=snr, seed=101, batch=2000 if sh == 'x16' else 1000,
                          pri=3.0, a5=True))
J.sort(key=lambda j: (j['pri'], j['set'], j['shape'], j['method'], j['snr']))
plan = dict(host='hostB', amendment='A5 (+A5.1)', tuned_file='<SCRATCH>/ap_ber_20261024/results/tuned_a5.json', jobs=J)
json.dump(plan, open(sys.argv[1], 'w'), indent=0)
import collections
print(len(J), dict(collections.Counter(j['set'] for j in J)), 'cpu', sum(j['method'].startswith('kbest') for j in J))
