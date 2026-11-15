#!/usr/bin/env python3
"""A5.9 analysis. Usage: analyze_a59.py RUNS_DIR OUT.json"""
import json, os, sys
RUNS, OUT = sys.argv[1], sys.argv[2]
XF_HELD = {'p1': 0.8619977732264821, 'p2': 0.6490141877206038}       # A5.5 analysis.json, B = 1 F-R picks, mean over K
D = {'p1': 32, 'p2': 64}


def load(stim, eng, A):
    return json.load(open(os.path.join(RUNS, '%s_%s_a%d_d%d' % (stim, eng, A, D[stim[:2]]), 'cycles.json')))


res, bad = {}, []
for pt in ('p1', 'p2'):
    r = {}
    for A in (1, 4):
        arpeggio, chord = load(pt + 'arpeggio', 'arpeggio', A), load(pt + 'chord', 'v14', A)
        if not (arpeggio['all_pass'] and chord['all_pass']):
            bad.append('%s A=%d' % (pt, A))
        perK, xr, xm, lo, hi = {}, [], [], [], []
        for K in ('1', '2', '3'):
            f, a = arpeggio['per_K'][K], chord['per_K'][K]
            m_arpeggio, m_chord = f['tests'] + f['F'], a['L'] + a['F']
            d = dict(arpeggio_cyc=f['cycles_per_anneal'], chord_cyc=a['cycles_per_anneal'], x_rtl=f['cycles_per_anneal'] / a['cycles_per_anneal'],
                     x_F_stim=m_arpeggio / m_chord, arpeggio_rtl_over_model=f['cycles_per_anneal'] / m_arpeggio, chord_rtl_over_model=a['cycles_per_anneal'] / m_chord,
                     arpeggio_tests=f['tests'], arpeggio_F=f['F'], chord_L=a['L'], chord_F=a['F'], chord_n1=a['n1'])
            if A == 1:
                lat_arpeggio = 3 * f['tests'] + 2 * f['F']
                d.update(lat_model_n1=lat_arpeggio / (3 * a['L'] + a['F'] + a['n1']), lat_model_n1_0=lat_arpeggio / (3 * a['L'] + a['F']),
                         lat_model_n1_L=lat_arpeggio / (4 * a['L'] + a['F']), chord_lat=a.get('lat_per_anneal'), arpeggio_lat=f.get('lat_per_anneal'),
                         chord_lat_over_3LFn1=a.get('lat_per_anneal', 0) / (3 * a['L'] + a['F'] + a['n1']))
                lo.append(d['lat_model_n1_L']); hi.append(d['lat_model_n1_0'])
            perK[K] = d; xr.append(d['x_rtl']); xm.append(d['x_F_stim'])
        x_rtl, x_f = sum(xr) / 3, sum(xm) / 3
        c = x_rtl / x_f
        e = dict(per_K=perK, x_rtl_stim=x_rtl, x_F_stim=x_f, c=c, x_hat=XF_HELD[pt] * c, x_F_held=XF_HELD[pt])
        if A == 1:
            e['lat_bounds_stim'] = [sum(lo) / 3, sum(hi) / 3]
            e['x_rtl_within_lat_bounds'] = e['lat_bounds_stim'][0] <= x_rtl <= e['lat_bounds_stim'][1]
        xh = e['x_hat']
        e['class'] = 'edge' if 0.97 <= xh <= 1.03 else ('within' if xh <= 1 else 'over')
        r['A%d' % A] = e
    res[pt] = r
cls = [res[p]['A%d' % A]['class'] for p in res for A in (1, 4)]
res['outcome'] = 'stopped: failed check ' + ', '.join(bad) if bad else ('1' if all(c == 'within' for c in cls) else '2/3')
json.dump(res, open(OUT, 'w'), indent=1)
for p in ('p1', 'p2'):
    for A in (1, 4):
        e = res[p]['A%d' % A]
        print(p, 'A=%d' % A, 'x_rtl_stim %.3f x_F_stim %.3f c %.3f x_hat %.3f %s' % (e['x_rtl_stim'], e['x_F_stim'], e['c'], e['x_hat'], e['class']),
              ' per K ARPEGGIO/CHORD rtl/model:', [(round(v['arpeggio_rtl_over_model'], 2), round(v['chord_rtl_over_model'], 2)) for v in e['per_K'].values()],
              (' lat bounds %.3f-%.3f within %s' % (*e['lat_bounds_stim'], e['x_rtl_within_lat_bounds'])) if A == 1 else '')
print('outcome', res['outcome'])
