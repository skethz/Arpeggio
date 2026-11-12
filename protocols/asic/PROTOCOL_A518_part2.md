# PROTOCOL A5.18, part 2: Arpeggio rows for Table IV (BER, cycles, power) on the same-period layouts

Written and frozen on 11 Nov 2026 (05:25 CET), before any Arpeggio replay, activity or power run of A5.18. Part 1 (`PROTOCOL_A518.md`, dcb2104b…) and its amendment A1 (`AMENDMENTS_A518.md`, 0320a7f2…) stay as frozen. The go was the user's "Start both" (11 Nov 2026), approving `../PLAN_A517_A518_20261111.md` (stage R4/R5). **The paper does not change without the user.**

Known when this was written: C1 and C2 accepted at 1.00 ns, so the D = 32 and D = 64 primary pairs are at 1.00 ns. N1, S128, S128bal and the D = 128 P&R runs have no result yet. No power, activity or replay number of any A5.18 layout exists.

## 1. What is produced
For each D, at the part 1 §4 primary pair:
- **one Arpeggio row** on the Table IV workload that D already serves (row 3 P1 at D = 32; row 5 P2 at D = 64; row 6 64 users at D = 128), with every Table IV column;
- **like-for-like ratios** Arpeggio/Chord of time and energy per detection (both engines on the same stimulus source, as A5.11 §4–5).

Rows 1, 2 and 4 get no Arpeggio row: Arpeggio has no tuned setting there.

## 2. Frozen inputs (existing data, read before freezing)
**BER column: A5.13 fixed-point Arpeggio** (the arithmetic of its RTL), on Table IV's own channel uses (`ap_ber/results_a513/analysis.json`, 03785d7d…; per-batch files `results_a513_fixed/`):

| Row | Method | Uses | Bit errors | BER |
|---|---|---|---|---|
| 3 (P1) | `fafx_64_0.1_0.1_0_rand_32` | the 396,000 uses of Chord's row (seed 102, 198 batches) | 9,241 | 3.65e-4 |
| 5 (P2) | `fafx_32_0.1_0.1_0_rand_8` | 300,000 (seed 102) | 13,834 | 3.60e-4 |
| 6 (64 users) | `fafx_64_0.1_0.1_0_bal_8` | 300,000 (seed 344) | 20,405 | 2.66e-4 |

- Row 3 is checked first: the 198 batches must be the ones of Chord's 396,000-use X3P row. If they are not, the row uses the batches both runs cover and says so.
- The row note carries A5.16's fixed-over-float check at P1 (1.02× [0.93, 1.12], fails the ≤ 1.10 check).

**Cycle ratio x̂ (Arpeggio cycles per Chord cycle), per row:**
- **Primary:** x̂ = x_F × c.
  - x_F: A5.13's held-out `x_F_vs_prod` (the BER column's own runs): P1 0.848616, P2 0.648233, 64 users 0.558199.
  - c: A5.9's RTL/model factor at four contexts (A = 4): P1 0.993081, P2 1.044225; 64 users from W1 below.
  - So x̂ = 0.842744 (P1), 0.676901 (P2), 0.558199 · c_64 (64 users).
- **Also reported:** A5.9's float x̂ (0.856033, 0.677717), which the current V-B text uses.

**Chord's Table IV cycles per detection C_Ch,row** (RESULTS.md §4): 67,167 (row 3), 21,753.7 (row 5), 34,817.9 (row 6). Decisions per detection, as Table IV's pJ/dec column defines them, are taken from the same source.

## 3. New work
### W1. 64-user stimulus and c_64 (as A5.9 §3, D = 128)
- **Capture:** `capture_a59.py` with only the shape changed to x64 (MDI config from `mdi_solvers.MDI[('64x64', 16)]`, as `s2_counts.py`). Dev seed 9600, 22 dB, N_s 8, the same driver call and `to_fixed` arguments, 20 sub-problems per K. No held-out draw is read.
  - If the 14-bit assert (max |coef| < 2^13) fails, stop and report; no rescaling without an amendment.
  - Runs on hostB GPU3. The A5.17 S3 supervisor yields that GPU for the capture's minutes; its workers resume at batch level.
- **References** (`fa_ref59.py gen`, A59_R = 8):
  - `stim_x64fa`: S 64, T 0.1→0.1, q 0, start bal, mode fa (the A5.8 pick);
  - `stim_x64ap`: S 128, T 0.3→0.3, q 0.4, start rand, mode par (default Chord, `a56_128_0.3_0.3_0.4_0_alt_8`).
- **Verilator** (run_rtl_a59.sh flags, APE_PHILOX), A = 4, D = 128: `ape_engine_fa.sv` with `APE_FA_BAL`, and v1.4 `ape_engine.sv`. Each run must end ALL PASS on `fa_ref59.py check`.
- **c_64 = x_RTL / x_F,stim**, both means over K, by `analyze_a59.py`'s definitions.
- If the balanced-start check fails, c_64 comes from a random-start stimulus (`stim_x64far`: start rand, otherwise equal) and the row says so.

### W2. Activity (A5.11 §4 with A1/A2)
- **Existing, reused unchanged:** p1fa/p1ap (D = 32) and p2fa/p2ap (D = 64) SAIFs and their 1000 ps TCFs (`fa_a511/power/tcf/*_1000_netlist.tcf`).
- **New at D = 128:** Questa production runs of both engines on `stim_x64fa` and `stim_x64ap`, with `tb/tb_ape.sv`.
  - Arpeggio uses the build of the D = 128 entry: `APE_FA_BAL` if the entry is P128bal, otherwise the random-start build on the same stim.txt.
  - Pass 1 sets the window, pass 2 writes the SAIF (A5.11 A2 rule), both at 1000 ps.
  - Genus writes each TCF on that engine's synthesis DB: Chord `ape/syn/v14_d128_p1000`; Arpeggio the entry's synthesis DB.
  - Every run must accept all commands and return the expected beats.

### W3. Power (Innovus TT, `power_gate.tcl`, as `power_run.sh`)
Each TCF is rescaled to the layout's period by the duration token only (`tcf_rescale.py`).

| Run | Layout | TCF | Purpose |
|---|---|---|---|
| Q1 | Chord C1 (D32, 1.00 ns, hostC) | p1ap | D32 like-for-like |
| Q2 | Arpeggio C2 (D64, 1.00 ns) | p2fa | D64 like-for-like |
| Q3 | Arpeggio D128 entry | x64fa | D128 like-for-like |
| Q4 | Chord `ape_d128_p1200_r4` (hostC), or the Chord layout at the D128 pair period | x64ap | D128 like-for-like; control vs Table IV's 259.52 mW |
| Q5 | Chord C1 | Table IV's P1, P4s and P4m TCFs at 1000 ps | Chord's D32 rows at 1.00 ns, offered as an alternative (§5) |
| Q6 | Chord N1, if accepted | p2ap | the 1.15 ns D64 pair (also reported) |
| Q7 | every other accepted Arpeggio D128 layout | x64fa | also reported |

Existing power reused: Arpeggio `fa_d32_p1000` p1fa 96.87 mW; Chord `ape_d64_r4` p2ap 174.48 mW; the 1.15 ns D32 pair (A3: 76.92 / 70.63 mW); Arpeggio `fa_d64_p1150` p2fa 136.50 mW.

### W4. Sign-off (part 1 §5)
For C1, C2 and the D128 Arpeggio entry: LEC chain (RTL → fv_map → synthesis → routed), SS setup clock by `sta_ss_v3.tcl` (the same rules R1/R2 as Table IV's SS column), and the area breakdown (`area_public.txt`). Done before the rows are reported, not before the power runs.

## 4. Row assembly (formulas fixed here)
For an Arpeggio row at period T_A (f_A = 1/T_A), with power P_A from its own stimulus TCF:
- C_A = x̂ · C_Ch,row (cycles per detection);
- time per detection = C_A / f_A; energy per detection E = P_A · C_A / f_A;
- det/s/mm² = f_A / C_A / die_A;
- **decisions per detection** = Chord's row value × S_A / S_Ch, i.e. × 64/128 (row 3), 32/128 (row 5), 64/128 (row 6). One spin decision per lane per half-step, as Table IV defines it; the sub-problem counts are taken as Chord's. pJ/dec = E / decisions.
- Clock column: TT f_A (SS clock from W4).

**Like-for-like ratios** (A5.11 §5), per pair:
- ρ_t = x̂ · T_A / T_Ch (= x̂ at the same period);
- ρ_E = x̂ · e_A / e_Ch, with e = P · T per cycle and both P from the same stimulus source (p1fa/p1ap, p2fa/p2ap, x64fa/x64ap).
- **Check** (not primary): the same ratios with the production-run cycle ratio C_FA / C_AP from the pass-1 runs (A5.11: 0.846 at P1, 0.723 at P2; new at 64 users).

Every number is printed with its period and layout. A layout accepted after the closure pass is labelled "with one closure pass".

## 5. Decision terms (as A5.11 §6; this is a measurement)
Per D at the primary pair:
- **Arpeggio leads:** ρ_t < 1 and ρ_E < 1;
- **mixed:** one below 1, one above;
- **Chord leads:** both > 1.

**Table IV's Chord D = 32 rows** stay at 1.15 ns by default. Q5 gives them at 1.00 ns (C1) so the author can choose; the choice is the author's.

## 6. Predictions (frozen)
| Prediction | Probability |
|---|---|
| W1 checks ALL PASS for both engines at D = 128 | 0.8 |
| c_64 within 0.85–1.15 | 0.7 |
| D32 at 1.00 ns: ρ_E < 1 (Arpeggio leads) | 0.6 |
| D64 at 1.00 ns: ρ_E < 1 (Arpeggio leads) | 0.9 |
| D128: ρ_E < 1 (Arpeggio leads) | 0.75 |
| Q4 Chord control within ±3% of 259.52 mW | 0.6 |
| Chord C1 power on p1ap between 75 and 95 mW | 0.7 |

## 7. Outcome → text (author's call; previews only)
- Table IV gains up to three Arpeggio rows (about 6 column lines in the table*). The V-B routed parenthetical can then shrink to a pointer.
- The abstract's "26% less time" (each engine at its own clock) can be restated at the same clock from the D32 1.00 ns pair. Wording is the author's.
- If D128 has no accepted Arpeggio layout by part 1's stop rule (15 Nov 12:00 CET), Table IV gets the D32/D64 rows only.

## 8. Compute and safety (as part 1 §7)
- hostB: CPUs 0–23 only. P&R keeps priority. Verilator (-j 4) and Questa run at nice 10–19 on CPUs P&R leaves free; GPU3 only for the W1 capture.
- hostC: Q1, Q4, Q5 (the DBs live there), 4 CPUs each on CPUs mpstat shows idle.
- Kit-derived files move only server to server. HOME/XDG under `<SCRATCH>/antiphase_asic_20261017/home`.
- Outputs: `<SCRATCH>/antiphase_asic_20261017/a518/part2/` (hostB and hostC), log `a518/RUNLOG.txt`; W1 under `<SCRATCH>/ap_ber_20261024/a518_rtl/`.
- Never touch other users' or the user's other jobs.
