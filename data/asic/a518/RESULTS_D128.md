# A5.18 D = 128 (64 users): 1.20 ns pair

**Result: Arpeggio leads at D = 128.** At 1.20 ns, ρ_t = 0.718 and ρ_E = 0.845, both below 1.
Numbers come from `d128_rows.py` and are saved in `d128_pair_1200.json`.

## Pair
- **Arpeggio:** `closure/arpeggio_d128bal_a2_p1200_cl`. This is the P128bal balanced build at 1.20 ns **with one closure pass**.
  - TT setup: all +7.8 ps (reg2reg +9.6, reg2cgate +7.8, default +11.7), 0 violating.
  - Hold 0.000 ns, 0 violating; DRC 0; connectivity 0.
  - Die 0.7319 mm²; std logic 0.2431 mm².
- **Chord:** `chord_d128_p1200_r4` at 1.20 ns, Table IV's D = 128 layout. Die 0.7278 mm².

## Like-for-like ratios
- x̂_64 = x_F 0.558199 × c_64 1.286558 (`W1_bal.json`) = **0.718156**.
- **Power at 1.20 ns, both from the x64 stimulus:**
  - Arpeggio: 242.893 mW (x64arpeggio_a2 TCF 66422c0ca834).
  - Chord: 206.389 mW (x64chord).
  - Arpeggio draws 1.177× Chord's power.
- **ρ_t = 0.7182, ρ_E = 0.8452 → Arpeggio leads.**
- With the production-run cycle ratio, 291,594 / 539,220 = 0.5408, ρ_t = 0.5408 and ρ_E = 0.6364.

## Table IV row 9: Arpeggio (64 users, x64 22 dB, MDI N_s 8)
| | Arpeggio (1.20 ns, one closure pass) | Chord, Table IV printed row (1.20 ns) | ratio |
|---|---|---|---|
| BER | 2.66e-4 (20,405 / 76.8 M bits, seed 344) | as Table IV | |
| cycles / detection | 25,004.7 | 34,817.9 | 0.718 |
| time / detection | 30.01 µs | 41.78 µs | 0.718 |
| power | 242.89 mW (x64arpeggio_a2) | 259.52 mW (Table IV TCF) | |
| energy / detection | 7.288 µJ | 10.843 µJ | 0.672 |
| det/s/mm² (die, TT) | 45.5 k | 32.9 k | 1.384 |
| det/s/mm² at the SS clock | 30.4 k (1.80 ns) | 21.9 k (1.80 ns) | |
| decisions / detection | 1,511,522 (× 64/128) | 3,023,045 | |
| pJ / decision | 4.82 | 3.59 | 1.344 |
| die | 0.7319 mm² | 0.7278 mm² | 1.006 |

- Table IV's Chord row uses its own TCF, so the energy column (0.672) mixes stimulus sources. The like-for-like ρ_E (0.845) compares both engines on the same x64 stimulus.
- **pJ/decision is higher for Arpeggio** because it runs half the sweeps (64 vs 128) per detection. Each decision costs more; each detection costs less.

## Sign-off
- **SS setup clock** (`sta_ss_v3.tcl`, accept 1200):
  - R1: 1.80 ns for all groups (internal 1.80, monotone). R2: 1.90 ns for all groups (internal 1.80).
  - Chord's Table IV SS clock is 1.80 ns, so the two engines are equal under R1.
- **SS hold at 1.80 ns, R1:**
  - default (I/O) group: −67 ps, 1,745 paths. Chord's Table IV D128 shows −28 ps under R1.
  - reg2reg: −0.000 ns on 1 path (under 0.5 ps).
  - reg2cgate: +248 ps.
  - TT hold is clean (0 violating).
- **LEC syn → routed:** 46,778 / 46,778 Equivalent; 0 NEQ, 0 abort, 0 unknown.
- **LEC fv_map → synthesis netlist:** 46,778 / 46,778 Equivalent; 0 / 0 / 0.
- **LEC RTL → fv_map:** **Equivalent** (run `rtl_syn_r2`).
  - `lec.log`: "Compare Results: PASS", "Hierarchical Compare Result: Equivalent"; 0 aborted, no non-equivalent points.
  - The D = 128 Arpeggio engine passes RTL → fv_map → synthesis → routed equivalence.

## Other Arpeggio D = 128 layouts (own clock vs Chord at 1.20 ns)
| Layout | Period | Power (x64arpeggio_a2) | ρ_t | ρ_E |
|---|---|---|---|---|
| P130bal | 1.30 ns | 221.29 mW | 0.778 | 0.834 |
| P135bal | 1.35 ns | 210.65 mW | 0.808 | 0.825 |
| P155bal | 1.55 ns | 171.18 mW | 0.928 | 0.769 |

All three are below 1, so Arpeggio leads at its own clocks as well.
