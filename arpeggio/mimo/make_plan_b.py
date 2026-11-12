#!/usr/bin/env python3
"""Builds PLAN_B.json for the milestone-B timed cohort (PROTOCOL_B.md) from the scaling analysis (analyze_scale.py
--json) and the tuned schedules, by the protocol's rules:
- kernel items: 16x16 QPSK at 12 dB (RI, milestone A schedule; and DI, the MDI-Anechoic schedule), 16x16 16-QAM dDI at
  22 dB (milestone A schedule), and the massive-MIMO shape = the Nr > Nt i.i.d. configuration with the largest gap at
  BER 1e-3 between MMSE and the best detector, at its operating point; each as MMSE alone, the whole chain ('e2e')
  and the kernel alone, at the anneal counts listed;
- scaling items: for every configuration with an operating point, Anechoic at R* (whole chain, GPU) and K-best at
  K* (CPU), at that SNR;
- flips: instrumented runs of the kernel items at 16 anneals and of the massive shape at R*.
Usage: make_plan_b.py SCALE_SUMMARY.json OUT_PLAN.json"""
import json
import sys

summ = json.load(open(sys.argv[1]))


def best_sched(nt, nr, M, files):
    b = None
    for f in files:
        for l in open(f):
            r = json.loads(l)
            if 'best' in r or (r['nt'], r['nr'], r['M']) != (nt, nr, M):
                continue
            if b is None or r['ber'] < b['ber']:
                b = r
    s = b['sched']
    return {k: s[k] for k in ('S', 't0', 't1', 'q', 'kappa')}


T = '../results/tune_scale/'
RI_FILES = [T + 'tune.jsonl', T + 'tune_r2.jsonl']
DI_FILES = [T + 'tune_ddi_qpsk.jsonl']
Q16_RI = dict(S=128, t0=0.7, t1=0.5, q=0.6, kappa=0.0)
Q16_DI = dict(S=256, t0=0.3, t1=0.3, q=0.4, kappa=0.0)
X16 = dict(S=256, t0=0.3, t1=0.3, q=0.4, kappa=0.0)
mass = [(k, v) for k, v in summ.items() if v['nr'] > v['nt'] and v['rho'] == 0 and 'op_snr' in v]
gap = lambda v: (v['crossings']['mmse'][0] - v['best_snr']) if v['crossings']['mmse'][1] == 'ok' else 99
mk, mv = max(mass, key=lambda kv: gap(kv[1]))
m_kind = mv['R_kind']
m_sched = best_sched(mv['nt'], mv['nr'], mv['M'], DI_FILES if (m_kind == 'ddi' and mv['M'] == 4) else RI_FILES)
gpu = []
for name, nt, nr, M, snr, kind, sc, Rs, B in [
        ('q16_ri', 16, 16, 4, 12.0, 'ri', Q16_RI, [1, 4, 16, 64], 100000),
        ('q16_di', 16, 16, 4, 12.0, 'ddi', Q16_DI, [1, 4, 16], 100000),
        ('x16_ddi', 16, 16, 16, 22.0, 'ddi', X16, [1, 4, 16, 64], 100000),
        ('massive_' + mk, mv['nt'], mv['nr'], mv['M'], float(mv['op_snr']), m_kind, m_sched,
         sorted(set([mv['R'], 16])), 50000)]:
    gpu.append(dict(name=name, nt=nt, nr=nr, M=M, snr=snr, kind=kind, sched=sc, mode='mmse', batch=B))
    for R in Rs:
        for mode in ('e2e', 'kernel'):
            gpu.append(dict(name=name, nt=nt, nr=nr, M=M, snr=snr, kind=kind, sched=sc, mode=mode, R=R, batch=B))
cpu = []
for k, v in summ.items():
    if 'op_snr' not in v:
        continue
    kind = v['R_kind']
    sc = best_sched(v['nt'], v['nr'], v['M'], DI_FILES if (kind == 'ddi' and v['M'] == 4) else RI_FILES)
    B = 20000 if v['nt'] <= 32 else 10000
    gpu.append(dict(name='scale_' + k, nt=v['nt'], nr=v['nr'], M=v['M'], rho=v['rho'], snr=float(v['op_snr']), kind=kind,
                    sched=sc, mode='e2e', R=v['R'], batch=B, scaling=True))
    cpu.append(dict(name='scale_' + k, nt=v['nt'], nr=v['nr'], M=v['M'], rho=v['rho'], snr=float(v['op_snr']), K=v['K'],
                    batch=4000))
flips = [dict(g, R=16, batch=4000) for g in gpu if g['mode'] == 'e2e' and g.get('R') == 16 and not g.get('scaling')]
flips.append(dict([g for g in gpu if g['name'].startswith('massive')][0], R=mv['R'], batch=4000, mode='e2e'))
plan = dict(massive=dict(config=mk, rule='largest MMSE-to-best gap at BER 1e-3 among Nr > Nt i.i.d. configurations',
                         gap_dB=gap(mv), op_snr=mv['op_snr'], R=mv['R'], K=mv['K']), gpu=gpu, cpu=cpu, flips=flips)
json.dump(plan, open(sys.argv[2], 'w'), indent=1)
print('massive shape', mk, 'gap %.2f dB' % gap(mv), 'op SNR', mv['op_snr'], 'R*', mv['R'], 'K*', mv['K'])
print(len(gpu), 'GPU items,', len(cpu), 'CPU items,', len(flips), 'flip items')
