#!/usr/bin/env python3
"""PLAN_D.json for the milestone-D timed cohort, by the rules frozen in PROTOCOL_D.md, from the held-out seed-42 BER
results (results/ber_d/*_b.jsonl):
- points: P1 16x16 16-QAM 20 dB, P2 32x32 16-QAM 22 dB, P3 32x32 QPSK 14 dB (milestone C's matched-BER SNRs) and P4
  16x16 16-QAM 31.02 dB (their operating point, Eb/N0 25 dB);
- PIMI: both published-rule settings (hardware steps and 4x), torch and kernel chains; its matched-BER setting is the
  cheaper one with BER <= 1e-3 on seed 42, else the 4x setting, marked 'never';
- Antiphase (MDI): Ns 32 / 8 / 8 at P1-P3 (milestone C's cheapest, frozen), at P4 the cheapest Ns of {8, 16, 32, 64}
  with BER <= 1e-3 on seed 42 (else 64, 'never'); torch chain everywhere, kernel chain where the couplings fit (P1, P3, P4);
- Antiphase, one stage: at P4 the cheapest R of {1, 2, 4, 8, 16, 32, 64} with BER <= 1e-3 (else 64, 'never');
- ablation: variants ii, iii, iv at Antiphase's Ns per point (variant i is the Antiphase item itself), torch and kernel
  as for Antiphase;
- platform rows: the PIMI kernel alone (solver mode) and its chain at batch 10,000 for 8x8 and 16x16 16-QAM at their
  Table I hardware steps (32, 64), Eb/N0 25 dB.
Batches as milestone C: 500 (16x16), 250 (32x32 16-QAM), 2,000 (32x32 QPSK); draws seed 41,000,003, two batches cycled.
Usage: make_plan_d.py BER_DIR OUT.json"""
import glob
import json
import os
import sys

bdir, out = sys.argv[1], sys.argv[2]
rows = []
for f in glob.glob(os.path.join(bdir, '*_b.jsonl')):
    rows += [json.loads(l) for l in open(f)]


def ber(nt, M, snr, m):
    v = [r['ber'] for r in rows if r['nt'] == nt and r['M'] == M and abs(r['snr'] - snr) < 0.01 and r['method'] == m]
    assert len(v) == 1, (nt, M, snr, m, v)
    return v[0]


def cheapest(nt, M, snr, cands, fmt):
    for c in cands:
        if ber(nt, M, snr, fmt % c) <= 1e-3:
            return c, False
    return cands[-1], True


PTS = {'P1': ('16x16', 16, 16, 20.0, 500, (64, 256), 32, 8), 'P2': ('32x32', 32, 16, 22.0, 250, (128, 512), 8, 8),
       'P3': ('32x32', 32, 4, 14.0, 2000, (64, 256), 8, 8), 'P4': ('16x16', 16, 16, 31.0206, 500, (64, 256), None, 8)}
KERNEL_OK = {'P1', 'P3', 'P4'}
items, cheap = [], {}


def add(**k):
    k.setdefault('nb', 2); k.setdefault('seed', 41_000_003)
    k['id'] = '%s_%s_%s_%s%s_%s' % (k['point'], k['method'], k['impl'], k.get('variant', ''),
                                    k.get('steps') or k.get('Ns') or k.get('R'), k['mode'])
    items.append(k)


for p, (shape, nt, M, snr, B, steps, ns_c, w) in PTS.items():
    base = dict(point=p, shape=shape, nt=nt, M=M, snr=snr, batch=B)
    s_c, never = cheapest(nt, M, snr, list(steps), 'pimi%d')
    cheap[p] = dict(pimi_steps=s_c, pimi_never=never, pimi_ber={str(s): ber(nt, M, snr, 'pimi%d' % s) for s in steps})
    for st in steps:
        for impl in ('torch', 'kernel'):
            add(**base, method='pimi', impl=impl, mode='chain', steps=st, warps=w)
    if ns_c is None:
        ns, nev = cheapest(nt, M, snr, [8, 16, 32, 64], 'mdiane%d')
        R, rnev = cheapest(nt, M, snr, [1, 2, 4, 8, 16, 32, 64], 'aned%d')
        cheap[p].update(ane_ss_R=R, ane_ss_never=rnev, ane_ss_ber=ber(nt, M, snr, 'aned%d' % R))
        for impl in ('torch', 'kernel'):
            add(**base, method='ane_ss', impl=impl, mode='chain', R=R)
    else:
        ns, nev = ns_c, ber(nt, M, snr, 'mdiane%d' % ns_c) > 1e-3
    cheap[p].update(ane_Ns=ns, ane_never=nev, ane_ber=ber(nt, M, snr, 'mdiane%d' % ns))
    impls = ('torch', 'kernel') if p in KERNEL_OK else ('torch',)
    for impl in impls:
        add(**base, method='ane_mdi', impl=impl, mode='chain', Ns=ns)
        for v in ('ii', 'iii', 'iv'):
            add(**base, method='abl', impl=impl, mode='chain', Ns=ns, variant=v)
for nt, st, w in ((16, 64, 8), (8, 32, 4)):
    for mode in ('solver', 'chain'):
        add(point='plat', shape='%dx%d' % (nt, nt), nt=nt, M=16, snr=31.0206, batch=10000, method='pimi', impl='kernel',
            mode=mode, steps=st, warps=w)
json.dump(dict(items=items, cheapest=cheap), open(out, 'w'), indent=1)
print(len(items), 'items'); print(json.dumps(cheap, indent=1))
