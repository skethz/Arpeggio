#!/usr/bin/env python3
"""A5.17 S1 (PROTOCOL_A517.md section 5): free-commit bound, x'_0 = mean_K x_K * ref_K / L_K. No GPU, no free choices.
Usage: s1_free_commit.py OUT.json"""
import json, sys
B = '<LOCAL>/work/plan_20261024/ap_ber/'
PHI = {"x16": {"1": 0.12265701523344329, "2": 0.30423952902304086, "3": 0.39042388830532215},
       "x32": {"1": 0.22391417028777222, "2": 0.608402560916608, "3": 0.6797307931748036}}   # hostB results/tuned_a52.json flip_phi
REF4 = {'1': 379.286511094699, '2': 893.4824357640621, '3': 2038.7498551983783}                # hostB results/a58/select.json ref_cost
a = json.load(open(B + 'results_a514/analysis_a514_final_20261111.json'))
FL = json.load(open(B + 'data/a55/flips.json'))
L = lambda K: 256 * int(K)
ref = lambda sh, K: REF4[K] if sh == 'x64' else L(K) * (1 + PHI[sh][K])
# check L of re-tuned C1 from its calibration entry (steps / anneals)
c1 = FL['abl_ape_0.2_0.2_0.2_rand_8']
Lc1 = {K: v['steps'] / v['anneals'] for K, v in c1.items()}
assert all(abs(Lc1[K] - L(K)) < 1e-9 for K in Lc1), Lc1
def free(per, sh):
    pk = {K: x * ref(sh, K) / L(K) for K, x in per.items()}
    return dict(per_K=pk, x=sum(pk.values()) / len(pk), x_printed=sum(per.values()) / len(per))
A516 = a['A516_stage1']
out = dict(note='A5.17 S1 free-commit bound (Chord commits uncharged: C_Ch = L). x > 1: Arpeggio over free-commit Chord budget. '
                 'Q4: compare against re-tuned C1 at free commits (x = 1 by construction, L checked).', L_C1=Lc1)
out['Q1_P1'] = free(A516['P1']['float_x']['per_K'], 'x16')
out['Q2_P2'] = free(A516['P2']['float_x']['per_K'], 'x32')
out['Q3_64u'] = free(A516['P4']['float_x']['per_K'], 'x64')
q4a = free(a['A515']['x']['Astar']['per_K'], 'x32')
# re-tuned C1 with free commits costs L_K (its own L equals 256 K, checked above), so x' = mean_K L_K / L_K = 1
out['Q4_S76_vs_retuned'] = dict(arpeggio=q4a, retuned_C1_free=1.0, ratio=q4a['x'] / 1.0, retuned_C1_printed=a['A515']['x']['C1']['x'])
out['Q5_fixed'] = {p: free(A516[p]['fixed_x']['per_K'], sh) for p, sh in (('P1', 'x16'), ('P2', 'x32'), ('P4', 'x64'))}
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for k, v in out.items():
    if k.startswith('Q'):
        print(k, json.dumps(v, default=float)[:400])
