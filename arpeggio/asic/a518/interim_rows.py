#!/usr/bin/env python3
"""A5.18 part 2 (PROTOCOL_A518_part2.md 0d0eeeee) section 4 row assembly from unrounded inputs, D = 32 and D = 64 primary pairs
(1.00 ns) and D = 128 where available. Every input is copied from its source with the source named. Usage: interim_rows.py OUT.json"""
import json, sys

E = json.load(open('<LOCAL>/work/plan_20261024/antiphase_asic/data/energy_public.json'))
CH = {r['point']: r for r in E['rows']}                       # Chord Table IV rows (gate_r4)
XF = {'P1': 0.8486155347130092, 'P2': 0.6482332487627495, 'X64': 0.5581994345797335}   # A5.13 x_F_vs_prod
C = {'P1': 0.9930807561363328, 'P2': 1.0442250663188728}       # A5.9 A = 4 (A59.json)
C['X64'] = json.load(open(sys.argv[2]))['c_64'] if len(sys.argv) > 2 else None   # W1 (W1_bal.json)
XHAT_FLOAT = {'P1': 0.85603340042359, 'P2': 0.6777168832144369}  # A5.9 x_hat (float x_F held), V-B today
S_RATIO = {'P1': 64 / 128, 'P2': 32 / 128, 'X64': 64 / 128}   # Arpeggio sweeps / Chord sweeps (decisions per detection)
BER = {'P1': (9241, 396000 * 64), 'P2': (13834, 300000 * 128), 'X64': (20405, 300000 * 256)}   # A5.13 fixed Arpeggio
# power (mW, Innovus TT, unrounded) and layouts
PW = {
    'P1': dict(T_ns=1.0, layout_A='fa_d32_p1000', P_A=96.87219725, die_A=0.18733435968,       # fa_a511 p1fa_p1000
               layout_C='ape_d32_r4b + one closure pass (C1)', P_C_like=91.90603209,              # Q1 p1ap on C1
               P_C_tableIV_stim=92.81701010, die_C=0.19041774336),                               # Q5 P1 TCF on C1
    'P2': dict(T_ns=1.0, layout_A='fa_d64_p1000 + one closure pass (C2)', P_A=172.19181397, die_A=0.37818276288,   # Q2
               layout_C='ape_d64_r4', P_C_like=174.48015303, P_C_tableIV_stim=185.17531308, die_C=0.3655629536),  # fa_a511 p2ap; gate_r4
}
res = {}
for pt, w in PW.items():
    ch = CH[pt]['agreed']
    xh = XF[pt] * C[pt]
    T = w['T_ns']
    cyc = xh * ch['cycles_per_det']
    t_us = cyc * T / 1000.0
    e_uj = w['P_A'] * cyc * T * 1e-6
    dec = ch['decisions_per_det'] * S_RATIO[pt]
    row = dict(layout=w['layout_A'], period_ns=T, x_hat=xh, x_hat_float=XHAT_FLOAT[pt], ber=BER[pt][0] / BER[pt][1],
               cycles_per_det=cyc, time_per_det_us=t_us, power_mw=w['P_A'], energy_per_det_uj=e_uj,
               det_per_s_per_mm2_die=1e6 / t_us / w['die_A'], die_mm2=w['die_A'], decisions_per_det=dec, pj_per_decision=e_uj * 1e6 / dec)
    like = dict(rho_t=xh, rho_E=xh * w['P_A'] / w['P_C_like'], rho_t_float=XHAT_FLOAT[pt], rho_E_float=XHAT_FLOAT[pt] * w['P_A'] / w['P_C_like'],
                chord_layout=w['layout_C'], chord_power_like_mw=w['P_C_like'])
    like['term'] = 'Arpeggio leads' if like['rho_t'] < 1 and like['rho_E'] < 1 else ('Chord leads' if like['rho_t'] > 1 and like['rho_E'] > 1 else 'mixed')
    # Chord's Table IV row at the pair period (D32: C1 with the Table IV TCF; D64: the printed row)
    chord_row = dict(period_ns=T, cycles_per_det=ch['cycles_per_det'], time_per_det_us=ch['cycles_per_det'] * T / 1000.0,
                     power_mw=w['P_C_tableIV_stim'], energy_per_det_uj=w['P_C_tableIV_stim'] * ch['cycles_per_det'] * T * 1e-6,
                     die_mm2=w['die_C'])
    chord_row['pj_per_decision'] = chord_row['energy_per_det_uj'] * 1e6 / ch['decisions_per_det']
    in_table = dict(time=t_us / chord_row['time_per_det_us'], energy=e_uj / chord_row['energy_per_det_uj'],
                    vs_printed_row_time=t_us / ch['time_per_det_us'], vs_printed_row_energy=e_uj / ch['energy_per_det_uj'])
    res[pt] = dict(arpeggio_row=row, like_for_like=like, chord_row_same_period=chord_row, in_table_ratios=in_table)
json.dump(res, open(sys.argv[1], 'w'), indent=1)
for pt, r in res.items():
    a, l, c, i = r['arpeggio_row'], r['like_for_like'], r['chord_row_same_period'], r['in_table_ratios']
    print(pt, 'x_hat %.4f (float %.4f) BER %.3e cyc %.1f t %.2f us P %.2f mW E %.3f uJ det/s/mm2 %.3g pJ/dec %.2f' % (
        a['x_hat'], a['x_hat_float'], a['ber'], a['cycles_per_det'], a['time_per_det_us'], a['power_mw'], a['energy_per_det_uj'], a['det_per_s_per_mm2_die'], a['pj_per_decision']))
    print('   like-for-like rho_t %.4f rho_E %.4f (float %.4f / %.4f) %s; Chord same-period row: t %.2f us E %.3f uJ pJ/dec %.2f; in-table %.3f / %.3f; vs printed row %.3f / %.3f' % (
        l['rho_t'], l['rho_E'], l['rho_t_float'], l['rho_E_float'], l['term'], c['time_per_det_us'], c['energy_per_det_uj'], c['pj_per_decision'],
        i['time'], i['energy'], i['vs_printed_row_time'], i['vs_printed_row_energy']))
