#!/usr/bin/env python3
"""A5.18 part 2 W1: analyze_a59.py's definitions at D = 128, A = 4 only.
c_64 = x_rtl_stim / x_F_stim (means over K); x_hat_64 = x_F (A5.13 x_F_vs_prod, 64 users) * c_64. Usage: analyze_a518w1.py RUNS_DIR ARPEGGIO_RUN CHORD_RUN OUT.json"""
import json, os, sys
RUNS, ARPEGGIO, CHORD, OUT = sys.argv[1:5]
XF = 0.5581994345797335                     # results_a513/analysis.json points.P4.x_F_vs_prod
arpeggio = json.load(open(os.path.join(RUNS, ARPEGGIO, 'cycles.json'))); chord = json.load(open(os.path.join(RUNS, CHORD, 'cycles.json')))
perK, xr, xm = {}, [], []
for K in ('1', '2', '3'):
    f, a = arpeggio['per_K'][K], chord['per_K'][K]
    m_arpeggio, m_chord = f['tests'] + f['F'], a['L'] + a['F']
    d = dict(arpeggio_cyc=f['cycles_per_anneal'], chord_cyc=a['cycles_per_anneal'], x_rtl=f['cycles_per_anneal'] / a['cycles_per_anneal'],
             x_F_stim=m_arpeggio / m_chord, arpeggio_rtl_over_model=f['cycles_per_anneal'] / m_arpeggio, chord_rtl_over_model=a['cycles_per_anneal'] / m_chord,
             arpeggio_tests=f['tests'], arpeggio_F=f['F'], chord_L=a['L'], chord_F=a['F'])
    perK[K] = d; xr.append(d['x_rtl']); xm.append(d['x_F_stim'])
x_rtl, x_f = sum(xr) / 3, sum(xm) / 3
c = x_rtl / x_f
res = dict(arpeggio_run=ARPEGGIO, chord_run=CHORD, all_pass=bool(arpeggio['all_pass'] and chord['all_pass']), arpeggio_start=arpeggio.get('start'), per_K=perK,
           x_rtl_stim=x_rtl, x_F_stim=x_f, c_64=c, x_F_A513=XF, x_hat_64=XF * c, c_within_085_115=0.85 <= c <= 1.15)
json.dump(res, open(OUT, 'w'), indent=1)
print('all_pass', res['all_pass'], 'x_rtl_stim %.4f x_F_stim %.4f c_64 %.4f x_hat_64 %.4f' % (x_rtl, x_f, c, XF * c),
      'per K ARPEGGIO/CHORD rtl/model', [(round(v['arpeggio_rtl_over_model'], 3), round(v['chord_rtl_over_model'], 3)) for v in perK.values()])
