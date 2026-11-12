#!/usr/bin/env python3
"""A5.17 S2 analysis (PROTOCOL_A517.md sections 3-6): x'_k = mean_K c_K / (L_K + c_k,K), with c_K = x_K * ref_K Arpeggio's
held-out cycles per anneal (unchanged by k) and L_K + c_k,K Chord's k-row cost on the calibration draws that define ref_K.
Q4 uses re-tuned C1's own k-row cost per K as the denominator (as S1 used C1's L_K). Usage: s2_analyze.py S2.json S1.json OUT.json"""
import json, sys
S2, S1, OUT = (json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3])
assert all(S2['gates']['G1_G3'].values()) and all(v for k, v in S2['gates'].items() if k.startswith('G2')), S2['gates']
a = json.load(open('<LOCAL>/work/plan_20261024/ap_ber/results_a514/analysis_a514_final_20261111.json'))
A516 = a['A516_stage1']
R = S2['runs']
KS = ('c1', 'c2', 'c4', 'cinf')


def recost(per, run, chord=None):
    """per: Arpeggio x per K vs the default reference (run's L + c1); chord: denominator run (default: run itself)."""
    den = chord or run
    out = {}
    for k in KS + ('free',):
        pk = {}
        for K, x in per.items():
            ref = run[K]['L'] + run[K]['c1']                       # printed reference cost (G2: equals L (1 + phi) or ref_cost)
            d = den[K]['L'] + (0.0 if k == 'free' else den[K][k])
            pk[K] = x * ref / d
        out[k] = dict(per_K=pk, x=sum(pk.values()) / len(pk), fits=sum(pk.values()) / len(pk) <= 1.0)
    return out


res = dict(note='A5.17 S2: x\' <= 1 means Arpeggio fits within Chord\'s k-row cycles (free: commits uncharged). c1 reproduces the printed x.')
res['Q1_P1'] = recost(A516['P1']['float_x']['per_K'], R['default_x16'])
res['Q2_P2'] = recost(A516['P2']['float_x']['per_K'], R['default_x32'])
res['Q3_64u'] = recost(A516['P4']['float_x']['per_K'], R['default_x64'])
res['Q4_S76_vs_retuned'] = recost(a['A515']['x']['Astar']['per_K'], R['default_x32'], chord=R['retuned_C1_x32'])
res['Q4_check_common_denominator'] = {k: dict(arpeggio=a['A515']['x']['Astar']['x'],
                                              retuned=sum((R['retuned_C1_x32'][K]['L'] + (0 if k == 'free' else R['retuned_C1_x32'][K][k])) /
                                                          (R['default_x32'][K]['L'] + R['default_x32'][K]['c1']) for K in ('1', '2', '3')) / 3)
                                      for k in KS + ('free',)}
res['Q5_fixed'] = {p: recost(A516[p]['fixed_x']['per_K'], R[r]) for p, r in (('P1', 'default_x16'), ('P2', 'default_x32'), ('P4', 'default_x64'))}
res['chord_cost_ratio_k_over_1'] = {r: {K: {k: (v['L'] + v[k]) / (v['L'] + v['c1']) for k in ('c2', 'c4', 'cinf')} for K, v in R[r].items()}
                                    for r in R if isinstance(R[r], dict)}
res['round_histogram'] = {r: {K: v['frac'] for K, v in R[r].items()} for r in R if isinstance(R[r], dict)}
# consistency with S1 (free commits)
for q in ('Q1_P1', 'Q2_P2', 'Q3_64u'):
    assert abs(res[q]['free']['x'] - S1[q]['x']) < 1e-9, q
    assert abs(res[q]['c1']['x'] - S1[q]['x_printed']) < 1e-9, q
assert abs(res['Q4_S76_vs_retuned']['free']['x'] - S1['Q4_S76_vs_retuned']['arpeggio']['x']) < 1e-9
json.dump(res, open(OUT, 'w'), indent=1)
for q in ('Q1_P1', 'Q2_P2', 'Q3_64u', 'Q4_S76_vs_retuned'):
    print(q, '  '.join('%s %.3f%s' % (k, res[q][k]['x'], '' if res[q][k]['fits'] else '*') for k in KS + ('free',)))
for p, v in res['Q5_fixed'].items():
    print('Q5', p, '  '.join('%s %.3f%s' % (k, v[k]['x'], '' if v[k]['fits'] else '*') for k in KS + ('free',)))
print('Q4 common-denominator check', {k: (round(v['arpeggio'], 3), round(v['retuned'], 3)) for k, v in res['Q4_check_common_denominator'].items()})
for r, h in res['round_histogram'].items():
    print(r, {K: {k: round(x, 3) for k, x in f.items()} for K, f in h.items()})
