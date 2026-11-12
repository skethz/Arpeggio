#!/usr/bin/env python3
"""Derive energy per detection, throughput and per-decision energy from the sanitized gate_r4 power summaries
(data/raw/power_*.json) and the cycle-exact workload counts (data/raw/workload/final_workload_public.json).
E = P x C x T (C = cycles per detection, all B detections, command replay; T = accepted clock period)."""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, '..', 'data')
wl = json.load(open(os.path.join(D, 'raw', 'workload', 'final_workload_public.json')))['cases']
ENG = {'d32': dict(D=32, T_ns=1.15, run='ape_d32_p1150_r4'), 'd64': dict(D=64, T_ns=1.00, run='ape_d64_r4'),
       'd128': dict(D=128, T_ns=1.20, run='ape_d128_p1200_r4')}
sta = json.load(open(os.path.join(D, 'sta_public.json')))
for k in ENG:
    s = sta.get(k.upper())
    ENG[k]['T_ss_ns'] = (s['ss_clock_ps'].get('all_groups') or s['ss_clock_ps'].get('all_groups_primary_R1')) / 1000.0 if s else None
PTS = {'P1': ('d32', 'P1_s41', 'P1_s241', 'x16 20 dB, MDI Ns 32 (G3/G4 gate point)'),
       'P4s': ('d32', 'P4s_s45', 'P4s_s245', 'x16 31.02 dB, one stage R 4 (matched-BER to PIMI HW)'),
       'P4m': ('d32', 'P4m_s45', 'P4m_s245', 'x16 31.02 dB, MDI Ns 8'),
       'P3': ('d64', 'P3_s43', 'P3_s243', 'q32 14 dB, DI Ns 8'),
       'P2': ('d64', 'P2_s42', 'P2_s242', 'x32 22 dB, MDI Ns 8'),
       'X64': ('d128', 'X64_s44', 'X64_s244', 'x64 22 dB, MDI Ns 8')}
rows = []
for tag, (eng, a, f, desc) in PTS.items():
    p = os.path.join(D, 'raw', 'power_%s_%s.json' % (eng, tag))
    if not os.path.exists(p):
        continue
    s = json.load(open(p)); e = ENG[eng]; T = e['T_ns'] * 1e-9; Dd = e['D']
    P = s['p_tt_mw'] * 1e-3
    out = dict(point=tag, engine=eng.upper(), desc=desc, clock_ns=e['T_ns'], f_mhz=1e3 / e['T_ns'], p_mw=s['p_tt_mw'],
               leak_mw=s['leak_tt_mw'], clock_network_mw=s['clock_network_mw'], clock_share=s['clock_network_share'],
               die_mm2=s['die_um2'] / 1e6, core_mm2=s['core_um2'] / 1e6, energy_per_cycle_pj=P * T * 1e12)
    for lab, key in (('agreed', a), ('fresh', f)):
        w = wl[key]; C = w['replay_cycles_per_det']; B = w['B']
        E = P * C * T
        dec = Dd * w['dops'] / B; upd = Dd * w['rport'] / B
        out[lab] = dict(seed=w['seed'], B=B, ber=w['ber'], cycles_per_det=C, time_per_det_us=C * T * 1e6, energy_per_det_uj=E * 1e6,
                        det_per_s=1 / (C * T), det_per_s_per_mm2_die=1 / (C * T) / out['die_mm2'],
                        det_per_s_per_mm2_core=1 / (C * T) / out['core_mm2'], decisions_per_det=dec, pj_per_decision=E / dec * 1e12,
                        lane_updates_per_det=upd, pj_per_lane_update=E / upd * 1e12,
                        ss_clock_ns=e['T_ss_ns'], det_per_s_at_ss_clock=(1 / (C * e['T_ss_ns'] * 1e-9)) if e['T_ss_ns'] else None,
                        det_per_s_per_mm2_die_at_ss_clock=(1 / (C * e['T_ss_ns'] * 1e-9) / out['die_mm2']) if e['T_ss_ns'] else None)
    rows.append(out)
json.dump(dict(method=__doc__, rows=rows), open(os.path.join(D, 'energy_public.json'), 'w'), indent=1)
for r in rows:
    g = r['agreed']
    print('%-4s %-5s P %.2f mW  E/cyc %.1f pJ  E/det %.4g uJ (fresh %.4g)  det/s %.4g (SS %.4g)  det/s/mm2 die %.4g core %.4g (SS die %.4g)  pJ/dec %.3f  pJ/upd %.2f  t/det %.4g us' % (
        r['point'], r['engine'], r['p_mw'], r['energy_per_cycle_pj'], g['energy_per_det_uj'], r['fresh']['energy_per_det_uj'], g['det_per_s'], g['det_per_s_at_ss_clock'] or 0,
        g['det_per_s_per_mm2_die'], g['det_per_s_per_mm2_core'], g['det_per_s_per_mm2_die_at_ss_clock'] or 0, g['pj_per_decision'], g['pj_per_lane_update'], g['time_per_det_us']))
