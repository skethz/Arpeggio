# PROTOCOL A5.5: equal-cycle SA, re-tuned per budget and first-accept (exploratory; not pre-registered in A5)
- **Written and frozen:** Thu 5 Nov 2026, 01:40 CET, for experiment 2.1 of `<PROJECT>/work/review_20261104/REVIEW_FINAL.md`, before any A5.5 tuning or held-out run and after the author's go in chat ("<instruction>"). Before this only the §12 checks, the §8 check on dev seed 9600, and a 17-cell smoke run on seed 1000 in a temporary folder ran; no grid, rule or prediction changed after them.
- **Hash:** SHA-256 in STATUS.md and `results/a55/SHA256SUMS_A55.txt` on hostB.
- **Unchanged:** every A5, A5.2, A5.3 and A5.4 number and verdict. A5.4's protocol forbids added arms, so this is separate. A5.4's numbers are not used here. `main.tex` changes only on the author's decision.

## 1. Why
The abstract's "2.3 to 17 times" rests on two choices the review says can block publication:
- **Schedule.** SA below 128 sweeps uses the 128-sweep pick compressed over S, not re-tuned (PROTOCOL_A5 §3, A53 §2). `mimo.geom` makes this worse at the low end: S = 1 runs T0 only, so both picks ran one sweep at T = 2.4; S = 2 runs T0 then T1, one hot sweep and one quench. The 17× is that S = 2 point.
- **Cost.** Eq. (4) charges SA one comparator per decision, S·N, while Antiphase's engine has D comparators.

**Question:** given a schedule chosen for its budget, and given the same comparators, what is SA's BER against Antiphase at about equal modeled cycles?

## 2. What the records already settle
**RTL read** (`ape_engine.sv` v1.4, SHA-256 `67367973…`, the same file as the accepted gate inputs on hostC). This answers review item 3.3:
- **"Pop one m from F" is a one-cycle find-first.** `f1_lb = lowbit(cpend)` drives `g_addr` in stage F1; it takes the lowest pending lane. The R port issues one row per cycle and F2 applies it. This path is in the routed D = 32, 64, 128 engines.
- **A re-test needs a decision slot.** `cw` is written at the F2 edge, then D0, D1 (registers `d1_sw`), D2 (compare). The decision port takes one context per cycle with latency 3. So a flip costs one row update and one re-test in Eq. (4)'s units, and 5 cycles of latency on a single context.
- **The comparator is rule (2).** T comes from a per-step table and q per context, so cooling needs no new hardware. Metropolis does: the only Metropolis RTL here is `sa_metropolis.sv`, a primitive with a 1,025-entry ROM and a 25×40 multiply, unsynthesized and in no engine.
- **Random numbers.** The production stream advances in D1, so a re-test draws anew. The law does not change: lanes after m are uncommitted, and their draws are independent of m being first. The Philox build is counter-based and holds r per pass.
- **Edits a first-accept engine needs:** a per-context scanned-lane mask, dropping the rest of F after F1, and a return to D0 with `ck` held until the pass ends. None has been synthesized.

**Exact sequential semantics.** `sa_seq` visits i = p·D + m in index order with one random number per spin per sweep (`mimo.anechoic` and `spins_to_levels_delta` confirm the layout). First-accept with those numbers rejects the same lanes before m, commits m, and re-tests later lanes on the updated field. So first-accept Metropolis should be **bit-identical** to `sa_seq` (§12). One set of Metropolis runs then serves both cost models; only the x-axis differs.

**Existing series under both models** (no new run; x over K = 1–3; ratio to (i) [95 % CI]). P1 old pick, P2 sa2:

| S | P1 x_E | P1 x_F | P1 ratio | P2 x_E | P2 x_F | P2 ratio |
|---|---|---|---|---|---|---|
| 1 | 0.30–0.37 | 0.25–0.30 | 26.3 [20.8, 34.9] | 0.50–0.68 | 0.41–0.55 | 23.1 [18.5, 29.4] |
| 2 | 0.51–0.62 | 0.31–0.36 | 6.22 [4.83, 8.41] | 0.83–1.16 | 0.48–0.69 | 17.3 [13.9, 22.0] |
| 4 | 0.95–1.11 | 0.47–0.48 | 2.30 [1.71, 3.13] | 1.48–2.00 | 0.60–0.77 | 5.52 [4.20, 7.12] |
| 8 | 1.86–2.13 | 0.75–0.89 | 1.62 [1.22, 2.21] | 2.87–3.78 | 1.02–1.09 | 3.07 [2.36, 4.00] |
| 16 | 3.69–4.16 | 1.31–1.71 | 1.17 [0.89, 1.56] | 5.71–7.36 | 1.75–2.10 | 1.92 [1.49, 2.46] |
| 32 | 7.35–8.22 | 2.42–3.37 | 0.87 [0.66, 1.14] | 11.4–14.5 | 3.07–4.09 | 1.06 [0.83, 1.35] |

**Antiphase re-tune.** `abl_colk_1_<Ns>` exists (q 0.2, T 0.2): P1 0.97 [0.75, 1.28], P2 0.74 [0.58, 0.93] against (i). Its q lies on that grid's lower edge, so §5 widens it.

**Why S = 64 and 128 stay in.** Under model F rejections are nearly free. At S = 128, S·P = L, so C_F = L + 2·F_SA, below Antiphase's L + F whenever 2·F_SA < F. The reported hot picks are far from that (F_SA 18–38× F at S = 128); a cold schedule may not be.

## 3. Cost models
Per anneal, in Eq. (4)'s units: one per decision step, one per row update.

| Model | Cost | Applies to | Status |
|---|---|---|---|
| E | S·N + F_SA | Metropolis | Eq. (4) as printed |
| F | tests + F_SA, tests = S·P + flips not on a pass's last lane; ≈ S·P + 2·F_SA | Metropolis (F-M), rule (2) (F-R) | **cost model** until §8 passes; no timing, area or energy |
| Antiphase | L + F, L = 128·P | all | P1 287 / 668 / 1,068; P2 313 / 824 / 1,290; P3 329 (K = 1) |
| Parallel trial | I·(1 + ⌈log₂ N⌉) | parallel trial | as A5 |

- **x** = cost / (L + F of (i)); budgets use the mean over K, and every K is reported.
- **F-R is the only arm on the existing comparators.** F-M needs a Metropolis unit per lane, which the model does not charge, and the text must say so.
- **Latency sensitivity** (picks only): first-accept 3·tests + 2·F_SA against Antiphase 3·L + F + n₁, with n₁ the half-steps holding at least one flip. On the existing series, x_lat/x_F is 0.87–1.15.

## 4. Arms
All inside the unchanged MDI wrapper (`mdi_diag`), with the existing Ns: P1 x16 20 dB Ns 32; P2 x32 22 dB Ns 8; P3 q32 14 dB Ns 8.

| Arm | Method | Rule | Budget |
|---|---|---|---|
| Metropolis first-accept = sequential SA | `abl_fam_<S>_<T0>_<T1>_<st>_<Ns>` | min(1, exp(−ΔE/T)) | S sweeps |
| Rule (2) first-accept | `abl_far_<S>_<T0>_<T1>_<q>_<st>_<Ns>` | s·u + q < r, r ~ U[−2T, 2T) | S sweeps |
| Antiphase | `abl_ape_<T0>_<T1>_<q>_<st>_<Ns>` | as (i) | L = 128·P |
| Parallel trial, balanced start | `abl_ptb_<cyc\|fl>_<T0>_<T1>_<Ns>` | as A5 | A5's budgets (a), (b) |

- **Starts `st`:** `rand` as now; `bal`: each coordinate gets P/2 copies +1 and P/2 −1, uniform and independent per coordinate and anneal, so d = 0 and the first candidate is the guess x_g. Parallel trial runs `bal` only; its `rand` results exist (A5, A5.2).
- **T steps per sweep** for first-accept, as `sa_seq`; per half-step for Antiphase and per iteration for parallel trial, as now.
- **Best state** after each pass, as `sa_seq`.
- **Code:** new `src/apx55.py` and `src/runner_a55.py`, which runs `src/runner.py` unchanged as A5.4 does. `src/a55_plan.py` is a pure function of the saved results: it queues what can run next and writes `results/a55/select.json`. `apx.py`, `runner.py` and `mimo.py` are not edited; A5.4's workers load them. Results go under `results/a55/`.

## 5. Tuning
**One pick per (arm, S, point), used for every K.** Antiphase has one schedule for every K and point, so this is more than its privilege. Per-K schedules are not tested.

**Grids.**
- **Metropolis,** S ∈ {1, 2, 3, 4, 8, 16, 32, 64, 128}: T0 ∈ {0.15, 0.3, 0.6, 1.2, 2.4, 4.8} × T1 ∈ {0.0125, 0.05, 0.15} with T1 < T0, plus constant T ∈ {0.05, 0.1, 0.2, 0.3, 0.6}: 22 cells. It includes the old pick and sa2. At **S = 1** `geom` uses T0 only, so the cells are constant T ∈ {0.05, 0.1, 0.2, 0.3, 0.6, 1.2, 2.4}: 7 cells. At **S = 2** the two sweeps run at T0, then T1.
- **Rule (2),** S ∈ {4, 8, 16, 32, 64, 128} (below S = 4, x_F is under 0.5): constant T ∈ {0.05, 0.1, 0.2, 0.3, 0.5, 0.8} plus (T0, T1) ∈ {(0.6, 0.1), (1.2, 0.1), (1.2, 0.2), (2.4, 0.1)}, × q ∈ {0, 0.2, 0.4}: 30 cells.
- **Antiphase:** q ∈ {0, 0.1, 0.2, 0.4, 0.8} × constant T ∈ {0.1, 0.15, 0.2, 0.3, 0.5}, plus (T0, T1) ∈ {(0.6, 0.2), (0.6, 0.1), (1.2, 0.2)} × q ∈ {0.2, 0.4}: 31 cells. It includes (0.4, 0.3) and (0.2, 0.2).
- **Parallel trial:** the 18 cells of A5 and A5.2 per budget and point.
- **Starts:** every first-accept and Antiphase cell runs both.

**Prune (cost only).** At S ≥ 32, at P1 and P2, a cell runs only if a 100-use flip probe (seed 1000, one batch of 100 through the runner) gives mean x_F ≤ 4. S = 64 is probed only if the cell survived at S = 32, and S = 128 only if it survived at S = 64. Pruned cells are logged. Corner cells are not probed. The hot S = 64, 128 series stay available from A5 and A5.3.

**Stage A.** Seed 1000; flips counted in every cell:
- P1 4,000 uses, batch 2,000; P2 2,000 uses, batch 1,000.
- P3: the §6 stopping rule, batch 4,000. A5's 4,000 uses are too few here; (ix) saw 66 bit errors in 156,250 uses.

**Per-S picks:** lowest BER (at P1 and P2 the same as fewest bit errors; P3's use counts differ), then lowest rate of erroneous uses, then plan order. Per-S picks use stage A only.

**Corners.** A per-S pick on a grid edge adds the next cell beyond that edge, with its start and other settings held: T0 × 2, T1 / 2, constant T × 2 or / 2, q × 2, plus the combined step if the pick is on two edges. At most two rounds; a pick still on a corner is reported. Parallel trial has no corner steps.

**Budget picks.** For each model and arm (E; F-M; F-R) at P1, P2 and P3, and each budget B ∈ {0.5, 1, 2, 3}: the three stage-A cells with mean x ≤ B and lowest BER go to stage B. A budget no cell meets has no pick. The Antiphase cells per point, and the parallel-trial cells per budget and point, also send their top three to stage B.

**Stage B.** New tuning seed 1010, never used for reporting (no earlier plan uses it), until ≥ 30 erroneous uses or a cap of 20,000 uses (P3: §6 stopping rule). Same selection rule, on stage B alone, then method name. A5.3 is the reason: a tie at 25 bit errors and 7 erroneous uses picked sa2, ×2.34 worse on held-out uses.

## 6. Held-out
Seed 102, the draws of (i). One job per distinct cell.
- **Jobs:** per-S picks; budget picks; the Antiphase pick per point; Antiphase `bal` at frozen (0.4, 0.3); parallel-trial `bal` picks per budget and point.
- **Stopping, PROTOCOL §3.4:** ≥ 100 erroneous uses and ≥ 100 bit errors; minimum uses 8,000 / 4,000 / 8,000 at P1 / P2 / P3; batches 2,000 / 1,000 / 4,000; cap 10⁷ bits.
- **Reference:** (i) `mdiane<Ns>`, unchanged, as every other number in the paper.
- No re-tuning or added arm after a held-out result is seen.

## 7. Flips
For every held-out pick, at each K: F_SA, tests, accept fraction and x under each model, measured as A5.3c on seed 1000, batch index 50: 1,000 uses at P1, 500 at P2, 2,000 at P3 (`src/calib_flips_a55.py`, once the held-out list is final). Parallel trial has no flip counter here; its budgets are A5's. This answers review item 3.2 for the new arms.

## 8. RTL check (D = 32)
- **What:** `ape_engine_fa.sv`, a copy of v1.4 with only the §2 edits (plus the seeder change if a reported pick uses `bal`), in behavioural simulation with `APE_PHILOX`, D = 32, A = 1 and 4. hostB CPU only, `iverilog` or `verilator`, under `<SCRATCH>/ap_ber_20261024/rtl_a55/`. No kit data is needed.
- **Stimulus:** dev seed 9600, P1, K = 1, 2, 3, 20 sub-problems each, against a fixed-point reference `fa_ref.py`.
- **Passes if:** the accepted-lane sequence matches the reference bit for bit; decision-port and R-port occupancy per anneal equal tests and F exactly; at A = 1, cycles equal 3·tests + 2·F. Best-state checks are gated to pass ends for this comparison; the v1.4 check fires on every decision.
- **Not covered:** synthesis, timing, area, energy (review 2.6). So the paper may say "cost model confirmed in RTL simulation", not "the same clock" or "the same energy".
- **If it fails:** model F stays a labelled model, the cause is reported, and the text may not say "on the same comparators".

**Result, before launch (`rtl_a55/RESULT.txt`, `rtl_a55/SHA256SUMS_RTL_A55.txt`; Verilator 4.228, not simulated with a gate netlist). PASSED first time on the behaviour; the first cycle comparison was off by a constant 1 because my log started one cycle before READY, so it now counts from the anneal's first D0.**
- **Stimulus:** 20 real sub-problems per K at P1, seed 9600, 2 anneals each, 120 anneals per run. Rule (2) at (T0, T1, q) = (1.2, 0.1, 0.2), S = 8, and (0.2, 0.2, 0.2), S = 32; `rand` and `bal`; A = 1 and 4. Eight runs, 18,486–25,041 tests and 3,185–18,617 flips per run.
- **All eight, ALL PASS:** accepted-lane sequence, tests per pass, flips, tests = S·P + flips not on a last lane, best spins and energy, init ops; at A = 1, cycles from first D0 to OUTQ minus (3·tests + 2·F) is 0 for every anneal.
- **Baseline:** the same harness on unmodified v1.4 against the reference's parallel mode: ALL PASS at A = 1 and 4.
- **Negative controls, both FAILED as they must:** no scanned-lane mask (livelocks, stopped by a 2,000,000-cycle cap) and `APE_BUG` (energy update with the field after the flip).
- **`bal` seeder (`APE_FA_BAL`):** a uniform pattern of P/2 ones among P copies from one 32-bit word per lane, by multiply-and-shift into a 2/6/20-entry list; m = 0, so no init ops. Its bias is at most 2⁻³² per pattern.
- **Not covered:** the production xorshift stream, which draws anew on a re-test (same law, §2); synthesis, timing, area, energy.

## 9. Reported, and the rule for the text (fixed at freeze)
**Reported:** every stage A and B cell, and pruned and corner cells; each pick's BER, paired ratio to (i) with 95 % cluster-bootstrap CI over channel uses, and McNemar, as A5; x per K under each model; the latency sensitivity. Ratios to the Antiphase pick are secondary; (i) is primary because it is what the paper reports and it favours SA.

**Terms,** at a point and budget, for the ratio SA/(i):
- **Antiphase leads:** CI lower bound > 1.
- **SA leads:** CI upper bound < 1.
- **Otherwise:** no detected difference.

**Class of each point** (P1, P2) at B = 1:
- **Both:** Antiphase leads under E and under F-R.
- **E-only:** Antiphase leads under E, not under F-R.
- **None:** Antiphase does not lead under E.

| Outcome | Abstract, Results, Conclusion | Table I, SA row | Contribution 3 and Sec. V-B |
|---|---|---|---|
| Both at P1 and P2 | "a to b times lower" against SA "re-tuned per budget", a, b from F-R | "Antiphase wins; not throughput" stays, unless the next rule removes it | Stay; stronger than now |
| E-only at one or both, None at neither | "Against one-comparator SA re-tuned per budget, a to b times"; say that first-accept on the same comparators closes the gap, at which points | "Ahead of one-comparator SA; first-accept SA ties or wins; not throughput" | Parallel decisions pay only where each sequential decision costs a cycle; V-B's run-in changes |
| None at either | No ratio in the abstract; per-point ratios in Results, naming only points that qualify | "No lead at equal modeled cycles" | Rewritten; whether framing B stands goes to the author first |

- **"Antiphase wins" leaves Table I** if, at any B ≤ 3 at P1 or P2, under E or F-R, a pick's ratio estimate is ≤ 1. Contribution 3 is then rewritten. If SA leads there, the text says so.
- **2.3 and 17 are retired as headline numbers in every outcome.** They may appear only in Sec. V-B, labelled "schedule chosen at 128 sweeps".
- **Quoted ratios carry** point, SNR, Ns, actual x and CI, including the 17× replacement, which has none today (review 1.3). F-M is quoted only with "a Metropolis unit per lane".
- **P3** is reported per point. No range in the abstract includes it unless the author decides so.
- **Fig. 3(a,b):** Antiphase star at (1, 1); new SA series under E and under F, F-R and F-M marked apart; the compressed series stays as a gray reference. A5.4's series is added only by its own rule and the author's decision. **Fig. 1(c)** follows Fig. 3 and its labels.
- **Other sentences these results touch:** abstract `main.tex:64`, Results :113, Eq. (4) and text :272–276, V-B :485–489, Conclusion :574. Page limits still apply: p1 is at a threshold, p6 has no spare line, and the abstract must be recounted (~100 words).
- **The author chooses the words.** These rows set what the evidence allows.

**Fallback (review 2.1)** if the results are not complete by **Tue 10 Nov, 18:00 CET**, for the abstract due 12 Nov, 02:00 CET: the abstract adds "against a one-comparator cost model and an SA schedule chosen at 128 sweeps", and Table I reads "Antiphase ahead in this cost model; no hardware comparison".

## 10. Predictions (frozen at freeze; my estimates)
**Ratios at B = 1:**
- P1, E: 1.2–2.5; Antiphase leads (P 0.75).
- P2, E: 3–12; below 10 (P 0.7), below 5 (P 0.35); Antiphase leads (P 0.9).
- P1, F-R: 0.6–1.5; Antiphase leads (P 0.2), SA leads (P 0.3).
- P2, F-R: 0.8–3; Antiphase leads (P 0.45), SA leads (P 0.1).

**Outcome rows:** Both at both points 0.12; E-only with no None 0.63; None at either 0.25.

**Estimate ≤ 1 at some B ≤ 3:** F-R at P1 (P 0.85), at P2 (P 0.6); E at P1 (P 0.35), at P2 (P 0.05).

**Others:**
- S = 1: a re-tuned constant T cuts BER ≥ 3× against T = 2.4 at P1 and P2 (P 0.9).
- `bal` beats `rand` in stage A at S ≤ 4 (P 0.8); at S ≥ 32 within 1.2× (P 0.6).
- Antiphase `bal` at (0.4, 0.3) is 0.8–1.2 of (i) (P 0.7). Antiphase pick: ≤ 0.8 at P2 (P 0.6); CI covers 1 at P1 (P 0.6).
- Parallel trial `bal`, equal cycles: at least 3× better than 14 (P2) and 2,500 (P3) (P 0.7); still behind (i) at P2 (P 0.7).
- F-M and F-R within 1.5× at the same budget (P 0.6).
- §8 passes first time (P 0.8); picks' x_lat/x_F within ±15 % (P 0.8).

These were written before any code ran and are unchanged, including the §8 one, which has since resolved (§8). The 17 smoke cells were read for rates and flip counts while they ran; they are not stage A, and their folder is not read by the selector.

## 11. Compute
BER only, untimed. No timing from this amendment is reported.

**The author's go, 5 Nov:** hostB GPU2 `<GPU_UUID>` and GPU3 `<GPU_UUID>`. At 01:35 CET both show 0 MiB of 32,607 MiB and no process. A5.4 stays on GPU0-1, untouched. GPU0-1 was the alternative, not chosen. GPU3 also serves another project, which has no job now.

**Limits, as A5.4:**
- `env_hostb_a55.sh` refuses any other GPU; occupancy is checked by UUID before launch.
- At most 4 workers per GPU plus one calibration process, 2 CPU threads each, each capped at 20 % of GPU memory. Peak in the replay: 1.3 GB.
- **Sharing:** workers do not yield to the other user's job. The supervisor launches nothing on a GPU with < 8 GB free and stops one of our workers if free memory falls below 2 GB; that worker resumes from saved batches. It never touches another user's process.
- A job that fails 3 times is left for inspection and logged. Everything stays under `<SCRATCH>`.

## 12. Checks before freezing (dev seeds 9600, 1000; saved held-out batches already reported)
**`src/test_a55.py`, ALL PASS required:**
- `fa_seq` Metropolis with `rand` is bit-identical to `sa_seq` on the same stream, including the flip count, at x16, x32, q32 and S ∈ {1, 2, 3, 8}.
- `abl_ape` with `rand`, T0 = T1 = 0.3, q 0.4 is bit-identical to `mdiane<Ns>`.
- `abl_ptb`'s kernel with `rand` is bit-identical to `snowball_par`.
- `bal` gives d = 0 for every coordinate and returns constellation levels.
- Rule (2) first-accept matches an explicit per-lane loop.
- Counters do not touch the random stream; tests = S·P + flips not on a last lane.

**`src/replay_a55.py`, ALL IDENTICAL required:** with `fa_seq` in place of `sa_seq`, batch 0 of `abl_sao_8_32` and `abl_sas_8_8` with the runner's seeds. Per-use bit errors and every erroneous x̂ match the saved arrays.

**If the identity fails,** F-M gets its own full tuning and held-out runs; the cost is reported to the author before launch.

**Results (5 Nov, GPU2-3, logs in `logs/a55/`):**
- **`test_a55.py`, ALL PASS, 151 checks (`test_a55_r2.log`).** The first run (`test_a55.log`) had 150 PASS and one FAIL: my threshold for the `bal` marginal, |mean| < 0.02, sat below the expected maximum of 5,120 means with σ = 0.022. The kernels did not change; the check became max |mean| < 5σ = 0.112 with grand mean exactly 0.
- **`replay_a55.py`, ALL IDENTICAL, 4 of 4:** batch 0 of `abl_sao_8_32`, `abl_sas_8_8`, `abl_sao_2_32`, `abl_sas_2_8`, including the S = 2 point behind 17×. So F-M uses the Metropolis runs, and no separate tuning is needed.
- **`sim_a55_plan.py`, SIM PASS:** the selector run to the end on synthetic results. No held-out job before tuning ends, seeds as stated, no pruned cell run, prune chain and corners terminate.
- **Reference costs reproduced:** from `tuned_a52.json`, P1 287 / 668 / 1,068, P2 313 / 824 / 1,290, P3 329.

## 13. Cost
Worker-hours from recorded `seconds` of `abl_sao_*`, `abl_sas_*`, `abl_sa_8` and tuning cells, which ran with up to 6 workers on a GPU. `fa_seq` tests a whole bank per step, so cold cells should run faster; S ≥ 64 at P2 assumes 3–5× and the rest assumes none.

**Measured in the smoke run (one worker, alone on the GPU), which suggests the table is conservative:** P2, 1,000 uses: Metropolis S = 128, T = 0.1, 85 s, against about 990 s for the hot series; rule (2) S = 128, 25 s; Antiphase 22 s. P1, 2,000 uses: Metropolis S = 128, 92 s; rule (2) S = 32, 26 s; Antiphase 17 s. P3, 4,000 uses: under 1 s for every cell tried.

| Block | Worker-h |
|---|---|
| Probes (at most 624 cells, 100 uses each) | ≈ 2 |
| Stage A: Metropolis 18.5, rule (2) ≤ 22, Antiphase 1.5, parallel trial 0.7 | ≤ 43 |
| Stage B: P1 3, P2 10 | ≈ 13 |
| Held-out: per-S picks 25, budget picks ≤ 10, Antiphase and parallel trial 2 | ≈ 37 |
| Flips (§7) | ≈ 2 |
| **Total** | **≈ 97** |
| If cold cells gain no speed | ≈ 150 |

**Wall clock:** 8 workers: about 12 h, 19 h worst case, from a launch at about 01:45 CET on 5 Nov. So results by the afternoon of 5 Nov, or the night of 5 to 6 Nov at worst, leaving about 6 days before the abstract. §8 is already done.

**Cuts if late, in this order (logged; the §9 rule does not change):**
1. Rule (2) at S = 128, P2.
2. Metropolis at S = 128, P2.
3. S = 64 at P2.
4. B = 0.5.
5. Parallel trial `bal`.

## 14. Not in this amendment
- **Per-K schedules:** about 3× the tuning.
- **Parallel-trial selector depth and synthesis:** review 2.7, its own item.
- **Routed sequential engine, PPA:** review 2.6.
- **Scan order other than the find-first order:** random-scan SA is not run; the hardware's order is the one under test.
- **Dilution kernels, Ns sweep:** review 1.1, 2.2.
- **A dB conversion for re-tuned picks:** the 0.4–1.4 dB sentence is at 128 sweeps.
