# PROTOCOL A5.8: first-accept SA on the same comparators at 64 users (P4), budget B = 1 (exploratory)

- **Author's go:** 7 Nov 2026, "<instruction>". It answered the coordinating session's question "Should I draft a frozen protocol for a 64-user test against first-accept SA?" and was relayed to this session with the instruction to draft, freeze and launch.
- **Written:** 7 Nov 2026, 00:47 CET (file time). Sections 1–8 and 10 were written before any A5.8 code ran; the first ran at 00:49. Section 9 was filled from the §12 checks and the dev-seed smoke (seed 9600: speed and flip counts only), and the smoke changed no grid, rule or prediction.
- **Hash:** SHA-256 in STATUS.md and `results/a58/SHA256SUMS_A58.txt` on hostB.
- **Unchanged:** every A5–A5.7 number and verdict. `main.tex`, the figures and the direction draft change only on the author's decision.

## 1. Question
At 64 users, at no more modeled cycles than Antiphase (cost model F, rule (2), the same D comparators), does first-accept SA re-tuned for that budget have lower or higher BER than Antiphase (i)?

**Why this point.**
- Both independent reviews (6 and 7 Nov) and the author's three-model consensus file rank first-accept SA on the same comparators as the main weakness.
- A5.5 at B = 1 (ratio SA/(i)):
  - P1: 0.464 [0.303, 0.666] at x_F 0.86, S 64, so SA leads.
  - P2: 1.03 [0.82, 1.30] at x_F 0.65, S 32, so there is no detected difference.
- A5.7 (the same stop and reinvestment for both) did not change this.
- 64 users is the only tested size where first-accept SA has not been run.

## 2. Point P4 and the reference
- **Workload:** 64×64 16-QAM at 22 dB with MDI Rmax 3, S 8, guesses mmse and sic (`mdi_solvers.MDI[('64x64', 16)]`, registered by `src/trace_x64.py`) and Ns = 8. This is the workload of Table IV row 6 and of A5.6 amendment 5.
- **Reference (i):**
  - Method `a56_128_0.3_0.3_0.4_0_alt_8` with stream `mdiane8`, which is the paper's Antiphase: L = 128·P, T 0.3, q 0.4, not re-tuned.
  - Held-out data are the saved X64F run: seed 344, batches of 500, 600 batches, 300,000 uses, 762 erroneous uses, BER 3.47 × 10⁻⁴. No new (i) held-out run is needed.
- **Held-out seed 344:** the paper's 64-user convention (X3T, X64F, X64S, X64K). Seed 102 has no 64-user draws.
- **Cost of (i), model F:** L_K + F_K per anneal.
  - Budget selection uses (i)'s flips on tuning seed 1000 (job `tunea`, below).
  - Reported held-out x uses X64F's own flips on seed 344. For reference, those give 379.8 / 900.1 / 2,015.8 at K = 1 / 2 / 3 (F/L 0.48 / 0.76 / 1.62).

## 3. Cost model
As A5.5 §3, model F, cost per anneal at K:
- **First-accept SA:** tests + flips. Here tests = S·P + flips not on a pass's last lane, measured on the run (`fa_seq` counters).
- **Antiphase:** L_K + F_K.

**x** = mean over K = 1–3 of cost_SA,K / cost_(i),K, as A5.5. Model F is a cost model confirmed in RTL simulation at D = 32 (A5.5 §8). It covers no timing, area or energy. D = 128 is not simulated here.

**Not in A5.8:**
- **E (Metropolis, one comparator):** it needs its own Metropolis grid, about doubling the compute, and it is not the weakness in question.
- **F-M:** it needs a Metropolis unit per lane.
- **Latency sensitivity:** n₁ is not counted by the trace path.

## 4. Arm and grid
- **Rule (2) first-accept:** `abl_far_<S>_<T0>_<T1>_<q>_<st>_8` (`src/apx55.py` `fa_seq`, rule 'r'), run through `src/trace_x64.py`, which is `trace_a56.py` unchanged with x64 registered.
- **Grid:** A5.5's rule-(2) grid.
  - Temperature: constant T ∈ {0.05, 0.1, 0.2, 0.3, 0.5, 0.8}, or (T0, T1) ∈ {(0.6, 0.1), (1.2, 0.1), (1.2, 0.2), (2.4, 0.1)}.
  - Then × q ∈ {0, 0.2, 0.4} (30 cells), × start ∈ {rand, bal}, × S ∈ {8, 16, 32, 64, 128}, for 300 cells.
  - S = 4 is left out: at B = 1 it can only be picked if S = 8 does not fit, which A5.5's flip counts rule out.
- **Prune (cost only):**
  - A cell with S ≥ 16 runs only if a 100-use probe (seed 1000, one batch of 100) gives mean x_F ≤ 1.25. The margin above B = 1 covers probe noise.
  - S = 32 is probed only if the same cell survived at S = 16, S = 64 only if it survived at 32, and S = 128 only if it survived at 64.
  - Pruned cells are logged. Corner cells are not probed.
- **Corners:** as A5.5 §5, but they extend the per-S stage-A pick **among cells within budget** (x_F ≤ 1), since only B = 1 is tested here. A pick on a grid edge adds the next cell beyond that edge, with at most two rounds. A pick still on an edge is reported.

## 5. Tuning (seeds 1000 and 1010, never used for reporting)
1. **`tunea` reference:** (i) on seed 1000, 8 batches of 500 (4,000 uses), with flips counted. It runs first, because the probes and budgets need its L_K + F_K.
2. **Stage A:** every surviving cell on seed 1000, 8 batches of 500 (4,000 uses), with flips counted.
3. **B = 1 pool:** every stage-A cell, corners included, with stage-A mean x_F ≤ 1. The three with the lowest BER go to stage B; ties are broken by the rate of erroneous uses, then by method name.
4. **Stage B:** seed 1010, batches of 500, until ≥ 30 erroneous uses or a cap of 20,000 uses. The same rule on stage B alone picks the **B = 1 pick**.
5. **Per-S stage-A picks** are reported (tuning seed only), not run on held-out data.

## 6. Held-out
- **Job:** the B = 1 pick on seed 344, batches of 500, batch indices 0–599 (X64F's 300,000 uses), split into twelve chunk jobs of 50 batches (`first_batch` 0, 50, …, 550).
- **Fixed length, no optional stopping.** This exceeds §6 of A5.5 (≥ 100 erroneous uses and ≥ 100 bit errors), which (i) meets after about 40,000 uses. At a ratio near 1, 100 erroneous uses would give a CI of about ±35 %; 300,000 uses gives about ±12 %.
- **Pairing:** with X64F batch by batch (same draws, same batch size).
- **A time cut (§9) uses every completed batch.** The stop time never depends on results.
- No re-tuning or added arm after any held-out result is seen.

## 7. Analysis (`src/analyze_a58.py`, written before any held-out result)
- **Ratio** SA/(i) of bit errors on the paired uses, with a paired cluster bootstrap (4,000 replicates, `a56an.boot_ratio`) and exact McNemar on erroneous uses.
- **Held-out x_F:** SA from its seed-344 counters, (i) from X64F's, mean over K. Stage-A x_F is also reported.
- **Also reported:** every probe, stage-A, corner and stage-B cell with its x_F per K; the pruned cells; the per-S picks.

## 8. Decision rule and what each outcome lets the text say (fixed now)
**Terms,** as A5.5 §9:
- **Antiphase leads:** the CI lower bound of SA/(i) is above 1.
- **SA leads:** the upper bound is below 1.
- **Otherwise:** no detected difference.

**Budget check.** If the held-out x_F of the B = 1 pick exceeds 1.10, the result is reported "at x_F = …". It may not be called "at no more modeled cycles".

The 16- and 32-user statement, "first-accept SA ties at 32 users and wins at 16", stays in every outcome. P4 enters the paper only by the author's decision, and if it enters it does so with its verdict, whatever that is.

| Outcome at P4 | What the text may say | What it may not say |
|---|---|---|
| Antiphase leads | "At 64 users (one point, Ns 8, cost model F, exploratory), first-accept SA re-tuned for the budget has a [lo, hi] times Antiphase's BER at x_F = …". Table I SA row: "first-accept SA ties or wins at 16–32 users, trails at 64 (exploratory)". | A trend or crossover size from one point. "Antiphase beats SA" without the size and model. Throughput, area or energy. |
| No detected difference | "First-accept SA wins at 16 users and ties at 32 and 64." | Any advantage over first-accept SA. |
| SA leads | "First-accept SA ties at 32 users and wins at 16 and 64." If the paper keeps any 64-user claim (Table IV row 6, the K-best sentence in V-C) and reports P4, it says so. | Nothing new for Antiphase. |

## 9. Checks before freezing, smoke, compute
*(Filled at 01:00–01:08 CET before the freeze. The smoke changed no grid, rule or prediction. It changed the held-out chunking only, from six chunks of 100 to twelve chunks of 50, so that all eight workers are used.)*

**Inherited scripts audited.** The following were read in full:
- `trace_a56.py` (`8639f53e…`)
- `trace_x64.py` (`b7196c0c…`)
- `a56lib.py` (`0ac6e07a…`)
- `apx55.py` (`8d0748ed…`)
- `a56an.py` (`f85ae126…`)

They are identical on hostB and in the local copies. `env_hostb_a56.sh` refuses any UUID other than GPU0 and GPU1.

**New code:**
- `a58_plan.py`, adapted from `a55_plan.py`: P4 only, rule (2) only, B = 1 only, held-out in chunks.
- `analyze_a58.py`.
- `supervise_a58.sh`.
- `sim_a58_plan.py` drives the planner to the end on synthetic results and returns **SIM PASS**:
  - the (i) reference runs first, with stream `mdiane8` and seed 1000;
  - tuning seeds are 1000 and 1010, held-out is seed 344;
  - the twelve chunks cover batches 0–599;
  - no pruned cell runs;
  - no held-out job starts before stage B ends.

**Checks on hostB, 00:49–01:04 CET, GPU0-1, all passed:**
- **Trace-path replay of A5.5's saved seed-102 batch 0 of `abl_far_32_0.1_0.1_0_rand_8` (P2): identical.** `trace_a56` checks bit errors and erroneous x̂ and raises on any mismatch.
- **`trace_x64` replay of X64F's saved batch 0 of (i): identical.**
- **Counter identity, tests = S·P·anneals + flips − last, holds** for every smoke cell at every K.

**Dev-seed smoke (seed 9600, one batch of 500 per cell, 9 workers on GPU0-1).**
- Shown are seconds per batch under 4–5-way sharing, model-F x against (i) on the same draws, and per-K x.
- The worker log also printed the cells' dev-seed error counts (0–7 erroneous uses per 500). They were not used for anything.

| Cell | s / 500 uses | x_F mean (K 1 / 2 / 3) |
|---|---|---|
| (i) | 75 | – (L + F 379 / 917 / 2,036) |
| S 8, T 0.1, q 0, rand | 158 | 0.44 (0.57 / 0.42 / 0.34) |
| S 32, T 0.1, q 0, rand | 309 | 0.80 (0.76 / 0.71 / 0.92) |
| S 64, T 0.1, q 0, rand | 427 | 1.19 (0.98 / 1.00 / 1.58) |
| S 64, T 0.1, q 0, bal | 390 | 0.57 (0.41 / 0.46 / 0.85) |
| S 128, T 0.1, q 0, rand | 846 | – |
| S 128, T 0.1, q 0, bal | 798 | – |
| S 32, (1.2, 0.1), q 0.4, rand | 677 | – |

These are the first measured x at P4, and they already depart from §10's cost model:
- The intercept for `rand` is about 0.3, not 0.54.
- K = 3 dominates: SA's F at K = 3 is 841–1,426 flips per anneal.
- With `bal`, S = 64 costs 0.57, so S = 128 `bal` cells may fit B = 1.

The predictions stay as written.

**Compute.** Each worker gets nice 10, 2 threads and a 20 % memory cap (peak about 2.5 GB). Estimated:

| Block | Estimate |
|---|---|
| Probes (≈ 185 × ≈ 120 s) | ≈ 6 worker-h |
| Stage A (≈ 250 cells × 8 batches at 150–850 s) | ≈ 145 worker-h, ≈ 18 h on 8 workers |
| Stage B (≤ 40 batches, run in parallel) | ≤ 10 h wall |
| Held-out (600 batches at up to 850 s) | ≤ 142 worker-h, ≈ 18 h on 8 workers |
| **Total** | **≈ 45 h wall**, from the launch at about 01:15 CET on 7 Nov to about 22:00 on 8 Nov, without yields |

**Hosts and limits:**
- hostB GPU0 `<GPU_UUID>` and GPU1 `<GPU_UUID>`. At 00:42 both showed 4 MiB used and no process.
- GPU2-3 run another user's jobs and are not used.
- 4 workers per GPU at 2 threads each make 16 threads, within <USER>'s 24-core cap.
- **Idle-with-yield:**
  - The supervisor starts no worker on a GPU that shows any compute process that is not ours.
  - It stops our workers there as soon as one appears. Batches are saved one at a time, and a stale claim is renamed on the next start.
  - It never touches any other process.
- A job that fails 3 times is left for inspection and logged. Everything stays under `<SCRATCH>`.

**Cuts if late, by clock time, never by results (logged):**
1. If stage A is not complete at **8 Nov 18:00 CET**, stage-A cells at S = 8 and S = 16 that have not yet started are dropped.
2. If stage B starts after **8 Nov 18:00**, its cap drops from 20,000 to 10,000 uses.
3. If the held-out run is not complete at **10 Nov 12:00 CET**, `analyze_a58.py` runs on every completed batch (§6).

The report then states the number of batches.

All three cuts are implemented: cuts 1 and 2 in `a58_plan.py` (`CUT1`, tested by `sim_a58_plan.py late`) and cut 3 in `supervise_a58.sh` (`CUT3`).

## 10. Predictions (written before any A5.8 code ran; my estimates)
**The coordinating session's hypothesis (from the A5.5 picks only).** SA's cost per sweep relative to Antiphase rose 1.5× from P1 to P2 (0.86/64 = 0.0134 against 0.65/32 = 0.0203). At D = 128, SA would get even fewer sweeps inside Antiphase's cycles, so Antiphase might lead.

**My cost model**, from A5.5's P2 picks and X64F's (i) flips:
- **x_F ≈ a + b·S.**
  - The intercept a is mostly the start's flips: about N/2 flips at 2 cycles each for `rand`, so a ≈ mean_K N_K / (L+F)_K.
  - At P2 this gives 0.34, which matches A5.5's P2 picks (0.65 at S 32, 1.57 at S 128).
  - At P4 it gives about 0.54 for `rand`, and much less for `bal`.
- **Slope b:** about 0.010 per sweep at P4, against 0.0096 at P2. Antiphase's own F/L rises from 0.22–0.68 at 32 users to 0.48–1.62 at 64, which offsets SA's extra flips.
- **So SA gets about as many sweeps at P4 as at P2, not fewer.** That is S ≈ 32 with `rand`, or up to 64 with `bal`.

| Claim | P |
|---|---|
| B = 1 pick has S = 32 | .45 |
| B = 1 pick has S = 64 | .35 |
| B = 1 pick has S ≤ 16 (the coordinating session's direction) | .15 |
| B = 1 pick starts `bal` | .45 |
| Stage-A x_F of the pick in [0.6, 1.0] | .9 |
| Held-out x_F within ±10 % of stage-A x_F | .85 |
| Ratio SA/(i) estimate in [0.6, 1.8] | .7 |
| **Antiphase leads** | **.30** |
| **No detected difference** | **.45** |
| **SA leads** | **.25** |
