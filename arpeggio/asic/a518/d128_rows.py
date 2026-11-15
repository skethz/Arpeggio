#!/usr/bin/env python3
"""A5.18 part 2 (PROTOCOL_A518_part2.md) section 4/5 for D = 128 (64 users, row 6) after amendment A5:
Arpeggio P128bal with one closure pass (closure/fa_d128bal_a2_p1200_cl, 1.20 ns) vs Chord ape_d128_p1200_r4 (1.20 ns).
Every input is copied unrounded from its source, named on its line. Usage: d128_rows.py W1_bal.json OUT.json"""
import json, sys

E = json.load(open('<LOCAL>/work/plan_20261024/antiphase_asic/data/energy_public.json'))
ch = {r['point']: r for r in E['rows']}['X64']['agreed']          # Chord Table IV row 6 (gate_r4, ape_d128_p1200_r4)
W1 = json.load(open(sys.argv[1]))                                   # hostB ap_ber_20261024/a518_rtl/W1_bal.json
XF = 0.5581994345797335                                             # A5.13 x_F_vs_prod, 64 users
c64 = W1['c_64']
assert abs(W1['x_F_A513'] - XF) < 1e-15 and W1['all_pass'] is True
xh = XF * c64

T_A = T_C = 1.2                                                     # ns, same clock (A5 primary pair)
P_A = 242.89264687        # Q3: x64fa_a2 TCF (66422c0ca834) on P128bal_cl, RUNLOG 07:53:50Z
P_C = 206.38892348        # Q4: x64ap TCF on ape_d128_p1200_r4 (control: Table IV TCF gives 259.51583 vs printed 259.52)
P_C_T4 = 259.51583214     # Chord Table IV row 6 power (Table IV stimulus TCF), energy_public.json
die_A = 0.7319283296      # closure/fa_d128bal_a2_p1200_cl/area_public.txt die_um2 731928.3296
die_C = 0.7277503584      # energy_public.json X64 die_mm2
C_FA, C_AP = 291594, 539220   # pass-1 production cycles, part2/act/x64fa_a2/pass1.txt and act/x64ap/pass1.txt
BER = (20405, 300000 * 256)   # part 2 section 2 row 6: fafx_64_0.1_0.1_0_bal_8, 300,000 uses seed 344
SS = dict(R1_all_ps=1800, R1_internal_ps=1800, R2_all_ps=1900, R2_internal_ps=1800,
          R1_hold_at_ss_ns=dict(all=-0.067, reg2reg=-0.000, reg2cgate=0.248, default=-0.067))   # part2/sta/P128bal_cl/result_public.txt
SS_C = 1.8                    # Chord Table IV row 6 SS clock (energy_public.json ss_clock_ns)

cyc = xh * ch['cycles_per_det']
t_us = cyc * T_A / 1000.0
e_uj = P_A * cyc * T_A * 1e-6
dec = ch['decisions_per_det'] * 64 / 128
row = dict(layout='fa_d128bal_a2_p1200 + one closure pass (P128bal_cl)', period_ns=T_A, x_hat=xh, x_F=XF, c_64=c64,
           ber=BER[0] / BER[1], cycles_per_det=cyc, time_per_det_us=t_us, power_mw=P_A, energy_per_det_uj=e_uj,
           det_per_s=1e6 / t_us, det_per_s_per_mm2_die=1e6 / t_us / die_A, die_mm2=die_A, decisions_per_det=dec,
           pj_per_decision=e_uj * 1e6 / dec, ss_clock_ns=SS['R1_all_ps'] / 1000.0,
           det_per_s_per_mm2_die_at_ss_clock=1e6 / (cyc * SS['R1_all_ps'] / 1e6) / die_A)
like = dict(rho_t=xh * T_A / T_C, rho_E=xh * (P_A * T_A) / (P_C * T_C), chord_layout='ape_d128_p1200_r4', chord_power_like_mw=P_C,
            power_ratio=P_A / P_C)
like['term'] = 'Arpeggio leads' if like['rho_t'] < 1 and like['rho_E'] < 1 else ('Chord leads' if like['rho_t'] > 1 and like['rho_E'] > 1 else 'mixed')
r_prod = C_FA / C_AP
check = dict(cycle_ratio_prod=r_prod, rho_t=r_prod * T_A / T_C, rho_E=r_prod * (P_A * T_A) / (P_C * T_C))
in_table = dict(time=t_us / ch['time_per_det_us'], energy=e_uj / ch['energy_per_det_uj'],
                pj_per_dec=(e_uj * 1e6 / dec) / ch['pj_per_decision'], area=die_A / die_C,
                det_per_s_per_mm2=row['det_per_s_per_mm2_die'] / ch['det_per_s_per_mm2_die'])
# Q7, also reported: other accepted Arpeggio D128 layouts at their own clocks vs Chord r4 at 1.20 ns (x64fa_a2 TCF rescaled)
Q7 = {'P130bal': (1.30, 221.28666634), 'P135bal': (1.35, 210.65445829), 'P155bal': (1.55, 171.18447304)}
also = {k: dict(period_ns=T, power_mw=P, rho_t=xh * T / T_C, rho_E=xh * P * T / (P_C * T_C)) for k, (T, P) in Q7.items()}
res = dict(primary_pair='1.20 ns', arpeggio_row=row, like_for_like=like, check_production_cycles=check,
           vs_tableIV_printed_row=in_table, also_reported_own_clock=also, ss=SS, chord_ss_clock_ns=SS_C,
           prediction=dict(text='D128: rho_E < 1 (Arpeggio leads), 0.75', held=like['rho_E'] < 1,
                           c64_band='0.85-1.15, 0.7', c64_in_band=0.85 <= c64 <= 1.15))
json.dump(res, open(sys.argv[2], 'w'), indent=1)
print('x_hat %.6f = x_F %.6f x c_64 %.6f' % (xh, XF, c64))
print('like-for-like 1.20 ns: rho_t %.4f rho_E %.4f (P_A/P_C %.4f) -> %s' % (like['rho_t'], like['rho_E'], like['power_ratio'], like['term']))
print('check (production cycles %.4f): rho_t %.4f rho_E %.4f' % (r_prod, check['rho_t'], check['rho_E']))
print('row: cyc %.1f t %.3f us P %.2f mW E %.4f uJ det/s %.1f det/s/mm2 %.1f (SS %.1f) pJ/dec %.4f BER %.3e die %.4f' % (
    cyc, t_us, P_A, e_uj, row['det_per_s'], row['det_per_s_per_mm2_die'], row['det_per_s_per_mm2_die_at_ss_clock'], row['pj_per_decision'], row['ber'], die_A))
print('Chord printed row: t %.3f us E %.4f uJ det/s/mm2 %.1f pJ/dec %.4f' % (ch['time_per_det_us'], ch['energy_per_det_uj'], ch['det_per_s_per_mm2_die'], ch['pj_per_decision']))
print('vs printed row: time %.4f energy %.4f pJ/dec %.4f area %.4f det/s/mm2 %.4f' % tuple(in_table[k] for k in ('time', 'energy', 'pj_per_dec', 'area', 'det_per_s_per_mm2')))
for k, v in also.items():
    print('also %s %.2f ns P %.2f mW rho_t %.4f rho_E %.4f' % (k, v['period_ns'], v['power_mw'], v['rho_t'], v['rho_E']))
