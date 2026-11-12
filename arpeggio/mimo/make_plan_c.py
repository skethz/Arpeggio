#!/usr/bin/env python3
"""PLAN_C.json for the milestone-C timed cohort (PROTOCOL_C.md), by the protocol's rules:
- (a) published Ns at fixed SNRs: 16x16 16-QAM 18/20/22 dB (Ns 64), 32x32 16-QAM 18/20/22 dB (Ns 128), 32x32 QPSK DI
  10/12 dB (Ns 64); both methods; PyTorch (all) and kernels (16x16 16-QAM, 32x32 QPSK); chain and solver-only modes;
- (b) matched BER at the fixed SNR of each shape (16x16 16-QAM 20 dB, 32x32 16-QAM 22 dB, 32x32 QPSK 14 dB): for each
  method the cheapest Ns of {8, ..., 256} whose BER on the seed-12 ladder is <= 1e-3 (if none, the largest, marked
  'never'); each method at its own cheapest Ns and at the other method's (equal budget); same implementations and modes;
- (c) 64x64 16-QAM at 22 dB, Ns 8, PyTorch, chain and solver-only.
Batches (same for both methods): 500 (16x16), 250 (32x32 16-QAM), 2,000 (32x32 QPSK), 125 (64x64); two distinct
batches of fresh draws per item (seed 31,000,003). Usage: make_plan_c.py OUT_PLAN.json [--dev]
(--dev: allow incomplete ladders, for a development plan)."""
import json
import sys

B = '../results/ber_c/'
LAD = (8, 16, 32, 64, 128, 256)


def ladder(files, shape):
    ber = {}
    for f in files:
        for l in open(B + f):
            r = json.loads(l)
            if r['method'].startswith('mdi'):
                ber[(r['method'][3:6], int(r['method'][6:]))] = r['ber']
    out = {}
    missing = [(m, ns) for m in ('ahc', 'ane') for ns in LAD if (m, ns) not in ber]
    if missing and '--dev' not in sys.argv:
        raise SystemExit('incomplete ladder for %s: %s' % (shape, missing))
    for m in ('ahc', 'ane'):
        ok = [ns for ns in LAD if ber.get((m, ns), 1.0) <= 1e-3]
        out[m] = dict(Ns=min(ok) if ok else max(LAD), meets=bool(ok), ber={ns: ber.get((m, ns)) for ns in LAD})
    return out


SH = {'16x16': dict(nt=16, M=16, batch=500), '32x32': dict(nt=32, M=16, batch=250),
      '32x32q': dict(nt=32, M=4, batch=2000), '64x64': dict(nt=64, M=16, batch=125)}
KERNEL = {'16x16', '32x32q'}
items = []


def add(point, sh, snr, Ns, method, impls, modes=('chain', 'solver')):
    s = SH[sh]
    for impl in impls:
        for mode in modes:
            items.append(dict(id='%s_%s_%g_%s%d_%s_%s' % (point, sh, snr, method, Ns, impl, mode), point=point,
                              shape=sh.rstrip('q'), nt=s['nt'], M=s['M'], snr=snr, Ns=Ns, method=method, impl=impl,
                              mode=mode, batch=s['batch'], nb=2))


impls = lambda sh: ('torch', 'kernel') if sh in KERNEL else ('torch',)
for sh, snrs, ns in (('16x16', (18.0, 20.0, 22.0), 64), ('32x32', (18.0, 20.0, 22.0), 128), ('32x32q', (10.0, 12.0), 64)):
    for snr in snrs:
        for m in ('ahc', 'ane'):
            add('a', sh, snr, ns, m, impls(sh))
match = {'16x16': (20.0, ['x16_b_ahc.jsonl', 'x16_b_ane.jsonl']), '32x32': (22.0, ['x32_b_ahc.jsonl', 'x32_b_ane.jsonl']),
         '32x32q': (14.0, ['q32_b.jsonl'])}
cheap = {}
for sh, (snr, files) in match.items():
    try:
        lad = ladder(files, sh)
    except FileNotFoundError:                                             # development plan before the ladders end
        print('ladder of', sh, 'not available: (b) items skipped')
        continue
    cheap[sh] = dict(snr=snr, **{m: lad[m] for m in lad})
    nss = sorted({lad['ahc']['Ns'], lad['ane']['Ns']})
    for m in ('ahc', 'ane'):
        for ns in nss:
            add('b', sh, snr, ns, m, impls(sh))
for m in ('ahc', 'ane'):
    add('c', '64x64', 22.0, 8, m, ('torch',))
json.dump(dict(items=items, cheapest=cheap), open(sys.argv[1], 'w'), indent=1)
for sh, c in cheap.items():
    print(sh, c['snr'], 'dB: AHC cheapest Ns %d (%s), Anechoic cheapest Ns %d (%s)' % (
        c['ahc']['Ns'], 'meets' if c['ahc']['meets'] else 'NEVER meets', c['ane']['Ns'], 'meets' if c['ane']['meets'] else 'NEVER meets'))
print(len(items), 'items')
