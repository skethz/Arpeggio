# A5.18 D = 128 (64 users): 1.20 ns pair after amendment A5 (13 Nov 2026)

**Verdict (part 2 §5): Arpeggio leads at D = 128.** At 1.20 ns, ρ_t = 0.718 and ρ_E = 0.845, both below 1.
The frozen prediction "D128: ρ_E < 1 (Arpeggio leads), 0.75" held.
Numbers come from `code_a518/d128_rows.py` (inputs unrounded, each source named in the script) and are saved in `d128_pair_1200.json`.

## Pair
- **Arpeggio:** `closure/fa_d128bal_a2_p1200_cl`. This is the P128bal balanced build at 1.20 ns **with one closure pass** (A5). It was accepted 13 Nov 08:48 CET.
  - TT setup: all +7.8 ps (reg2reg +9.6, reg2cgate +7.8, default +11.7), 0 violating.
  - Hold 0.000 ns, 0 violating; DRC 0; connectivity 0; FINAL.
  - Die 0.7319 mm²; std logic 0.2431 mm².
- **Chord:** `ape_d128_p1200_r4` at 1.20 ns, Table IV's D = 128 layout. Die 0.7278 mm².

## Like-for-like ratios (part 2 §4)
- x̂_64 = x_F 0.558199 × c_64 1.286558 (W1, `W1_bal.json`) = **0.718156**.
- **Power at 1.20 ns, both from the x64 stimulus:**
  - Arpeggio Q3: 242.893 mW (x64fa_a2 TCF 66422c0ca834).
  - Chord Q4: 206.389 mW (x64ap). The Q4 control on Table IV's TCF gives 259.516 mW, against 259.52 mW printed.
  - Arpeggio draws 1.177× Chord's power.
- **ρ_t = 0.7182, ρ_E = 0.8452 → Arpeggio leads.**
- **Check (not primary):** the production-run cycle ratio is 291,594 / 539,220 = 0.5408. With it, ρ_t = 0.5408 and ρ_E = 0.6364.

## Arpeggio row 6 (64 users, x64 22 dB, MDI N_s 8)
| | Arpeggio (1.20 ns, one closure pass) | Chord, Table IV printed row (1.20 ns) | ratio |
|---|---|---|---|
| BER | 2.66e-4 (20,405 / 76.8 M bits, seed 344) | as Table IV | |
| cycles / detection | 25,004.7 | 34,817.9 | 0.718 |
| time / detection | 30.01 µs | 41.78 µs | 0.718 |
| power | 242.89 mW (x64fa_a2) | 259.52 mW (Table IV TCF) | |
| energy / detection | 7.288 µJ | 10.843 µJ | 0.672 |
| det/s/mm² (die, TT) | 45.5 k | 32.9 k | 1.384 |
| det/s/mm² at the SS clock | 30.4 k (1.80 ns) | 21.9 k (1.80 ns) | |
| decisions / detection | 1,511,522 (× 64/128) | 3,023,045 | |
| pJ / decision | 4.82 | 3.59 | 1.344 |
| die | 0.7319 mm² | 0.7278 mm² | 1.006 |

- Table IV's Chord row uses its own TCF, so the energy column (0.672) mixes stimulus sources. The like-for-like ρ_E (0.845) compares both engines on the same x64 stimulus.
- **pJ/decision is higher for Arpeggio** because it runs half the sweeps (64 vs 128) per detection. Each decision costs more; each detection costs less.

## Sign-off (W4)
- **SS setup clock** (`sta_ss_v3.tcl`, accept 1200):
  - R1: 1.80 ns for all groups (internal 1.80, monotone). R2: 1.90 ns for all groups (internal 1.80).
  - Chord's Table IV SS clock is 1.80 ns, so the two engines are equal under R1.
- **SS hold at 1.80 ns, R1:**
  - default (I/O) group: −67 ps, 1,745 paths. Chord's Table IV D128 shows −28 ps under R1.
  - reg2reg: −0.000 ns on 1 path (under 0.5 ps).
  - reg2cgate: +248 ps.
  - TT hold, the acceptance criterion, is clean.
- **LEC syn → routed:** 46,778 / 46,778 Equivalent; 0 NEQ, 0 abort, 0 unknown.
- **LEC fv_map → synthesis netlist:** 46,778 / 46,778 Equivalent; 0 / 0 / 0.
- **LEC RTL → fv_map:** **Equivalent** (rerun `rtl_syn_r2`, amendment A6; finished 13 Nov 2026, 18:37 CET).
  - `lec.log`: "Compare Results: PASS", "Hierarchical Compare Result: Equivalent"; 0 aborted, no non-equivalent points; elapsed 21,752 s.
  - The first run was killed by its own 14,400 s guard while running `compare`. Datapath analysis had taken 7,786 s; no NEQ or abort had been reported.
  - For reference, Chord's D128 took 3 h 43 min in gate_r4.
  - The rerun used the same dofiles and a 43,200 s guard (hostB CPUs 17, 18, 20, 22), launched 13 Nov 12:33 CET.
  - With it, the D = 128 Arpeggio entry passes RTL → fv_map → synthesis → routed equivalence (W4 complete). Updated 15 Nov 2026 from STATUS.md (13 Nov, 18:37 CET).

## Also reported (Q7: other accepted Arpeggio D128 layouts, own clock vs Chord r4 at 1.20 ns)
| Layout | Period | Power (x64fa_a2) | ρ_t | ρ_E |
|---|---|---|---|---|
| P130bal | 1.30 ns | 221.29 mW | 0.778 | 0.834 |
| P135bal | 1.35 ns | 210.65 mW | 0.808 | 0.825 |
| P155bal | 1.55 ns | 171.18 mW | 0.928 | 0.769 |

All three are below 1, so Arpeggio leads at its own clocks as well.

## Predictions (part 2 §6)
- **c_64 within 0.85–1.15 (0.7): missed.** c_64 = 1.287. The RTL needs more cycles than the float model's x_F at 64 users, and x̂ still comes out at 0.718.
- **D128 ρ_E < 1 (0.75): held** (0.845).
- **Q4 control within ±3 % (0.6): held** (−0.002 %).

## Paper
main.tex is unchanged. Text changes are the author's call (part 2 §7, previews only).
