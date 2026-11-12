# A5.13: fixed-point BER of first-accept SA (frozen before any held-out batch)

**Request (user, 9 Nov 2026):** "<instruction>" The experiment is the first of the two I explained on 9 Nov: first-accept's fixed-point BER. The 32-user confirmatory re-test (first-accept vs. re-tuned Antiphase on new seeds) is separate and gets its own protocol.

**Why:** every first-accept BER in the paper is floating point: A5.5 at P1/P2, A5.8 at 64 users (P4). Antiphase also has a fixed-point, cycle-exact production model (X3P, Table IV). The Conclusion says "Pending its fixed-point BER and a 32-user re-test, first-accept is the policy to build." This run measures first-accept's BER with the first-accept RTL's integer arithmetic, in the production model's MDI wrapper, on the same draws as the saved runs.

**Exploratory status:** unchanged. The picks were made in A5.5/A5.8 on tuning seeds 1000/1010; nothing is re-tuned here.

## 1. Questions
1. **Primary:** against Antiphase's fixed-point production model on the same uses, does fixed-point first-accept keep the verdicts of floating-point first-accept?
2. **Quantization:** on the same uses, does fixed point change first-accept's BER?

## 2. What runs
**Engine:** `src/fa_fx.cu`, one CUDA thread per anneal. Statement for statement it is `fa_ref59.anneal`, mode 'fa' (rtl_a59/src/fa_ref59.py, sha256 b595b56c…), which the first-accept RTL matched event for event in A5.5 and A5.9.
- **Integers:** G and h come from `anefx.to_fixed` (Q = 4096) and `antiphase_ref.compress`, the same integers the production model gets.
- **Schedule:** T per pass is round(T·Q), with S sweeps × P passes, and q is round(q·Q), as in fa_ref59.gen.
- **Randomness:** Philox4x32-10 with counter (sweep/4, copy·D + lane, anneal, instance).
  - The instance is the use's index in the batch, as in production.
  - The key per solver call is (seed_base + call·0xD1B54A32D192ED03 + 0xA513) mod 2^64, with x3_prod.py's seed_base (draw seed × 0x9E3779B97F4A7C15).
- **Outputs:** best spins after each pass (start state excluded, as in the RTL), plus flips and comparator passes per anneal.

**Wrapper:** `src/run_a513.py`. It is x3_prod.py (A5.6 X3) with only the solver swapped. `mdi_logged` is unchanged, runs on the CPU with 4 torch threads, and draws with `apx.draw` on the CPU. The solver runs on hostA GPU7.

**Picks** (A5.5/A5.8 B = 1, rule (2), constant T = 0.1, i.e. 410/4096, q = 0):

| Point | Shape, SNR, N_s | Pick | Production comparator (X3P) |
|---|---|---|---|
| P1 | 16×16 16-QAM, 20 dB, 32 | abl_far_64_0.1_0.1_0_rand_32 | prod_fx_xs_32, seed 102, 200 × 2,000 |
| P2 | 32×32 16-QAM, 22 dB, 8 | abl_far_32_0.1_0.1_0_rand_8 | prod_fx_xs_8, seed 102, 300 × 1,000 |
| P4 | 64×64 16-QAM, 22 dB, 8 | abl_far_64_0.1_0.1_0_bal_8 | prod_fx_xs_8, seed 344, 600 × 500 |

**Held-out batches:** every saved X3P batch of each point, run in increasing index order:
- **P1:** 0–199, 400,000 uses.
- **P2:** 0–299, 300,000 uses.
- **P4:** 0–599, 300,000 uses, in four shards of 150.

The floating-point pick runs cover a prefix of these ("matched"): P1 0–13, P2 0–42, and P4 0–599. Batch sizes are the same, so the draws are identical. There is no stop on results, no re-tuning and no added arm.

**Host check (reported, not a decision input):** the production model is re-run on hostA for P1 0–13, P2 0–42 and P4 0–29 (`--solver prod`).

## 3. Compute
- hostA GPU7 only (env_ap.sh UUID). CPU: at most 24 threads in all (6 processes × 4), nice 10.
- Files go under <SCRATCH>/ap_ber_20261024/a513 only: `results/<tag>/fafx_…/snr_…/bNNNNN.npz` and `hostcheck/`.
- **Time cut:** if a point is not complete at **10 Nov 2026 12:00 CET**, the analysis uses every completed batch and the report states the count. The cut time does not depend on results.

## 4. Gates (all passed before any held-out batch; records in `gate/`)
- **G1, kernel bit-exactness (`gate/g1.json`):** PASS, 668 anneals, 0 mismatches in best energy, best spins, flips and comparator passes.
  - **G1a:** A5.5/A5.9's captured sub-problems at P1 (D = 32) and P2 (D = 64), K = 1–3, six per K, two anneals each. Cases: two keys (A5.9's and a random one) × rand/bal × two schedules (each pick's, and A5.9's hot 8-sweep 1.2→0.1, q = 0.2). 48 cases, 576 anneals, 107,748 flips.
  - **G1b:** real sub-problems recorded through `run_a513.detect` on dev seed 9600 at x16, x32 and x64 (D = 32, 64, 128), with the run's own keys and instance numbers. Two calls per K per shape, 92 anneals.
  - A first G1 attempt was stopped, unfinished and with no mismatch, because the recorded-wrapper part used torch's default threads (about 33 cores, above the cap). It was rerun complete with 4 threads.
- **G2, wrapper:**
  - (a) x64: run_a513 with the production solver reproduces X3P's saved batch 0, seed 344, per use: identical, 29 bit errors (`gate/g2_x64.json`).
  - (b) x16: the saved hostB batch 0, seed 102, differs in 3 of 2,000 uses (66 vs. 71 bit errors, `gate/g2_x16.json`).
  - (c) x16 driver check: the unchanged x3_prod.py (sha 2cc7515c…) run on hostA gives per-use bit errors, erroneous indices and x̂ identical to run_a513 (`gate/g2b_x16.json`). So (b) is a host floating-point difference (hostB vs. hostA CPU), not the driver.
  - Consequence: on a small fraction of uses, a hostA sub-problem can differ from hostB's. Pairing with X3P stays at the level of draws. The host check (§2) measures the rate.
- **Dev-seed probe (seed 1000, one batch per point, `probe/`):**

| Point | Seconds per batch | Erroneous uses / bit errors | Max coefficient, beyond 14 bits | C_FA per anneal (K = 1/2/3) |
|---|---|---|---|---|
| P1 | 5.7 | 5 / 37 | 4,096, 0 | 197.6 / 595.0 / 1,030.3 |
| P2 | 16.5 | 4 / 75 | 4,096, 0 | 172.2 / 558.2 / 900.6 |
| P4 | 72.1 | 1 / 46 | 4,096, 0 | 156.0 / 407.2 / 1,701.3 |

- **Known numbers on the same uses** (saved runs only, computed before this protocol): floating first-accept over production.

| Point | Uses | Ratio [95% CI] | Verdict |
|---|---|---|---|
| P1 | 28,000 | 0.441 [0.307, 0.597] | SA leads |
| P2 | 43,000 | 0.866 [0.694, 1.069] | no detected difference |
| P4 | 300,000 | 0.866 [0.789, 0.947] | SA leads |

## 5. Paired references
`refs/refs_a513.npz` (sha256 b5d1bd45…), extracted read-only on hostB by `src/extract_refs.py` (c6307f95…). Per batch it holds:
- X3P per-use bit errors and counters: P1 0–199, P2 0–299, P4 0–599.
- Floating first-accept: A5.5 abl P1 0–13, P2 0–42; A5.8 held0–11, P4 0–599.
- Floating Antiphase (i): abl mdiane32/mdiane8, continued by X3F (P1 0–197, P2 0–299); X64F (P4 0–599).

## 6. Estimators
`src/analyze_a513.py` (sha in SHA256SUMS_A513.txt) uses A5.6/A5.8's estimators:
- **Ratio:** fixed-point first-accept over the comparator, in bit errors on paired uses, with a paired cluster bootstrap (`a56an.boot_ratio`, 4,000 replicates, seed 12345).
- **McNemar:** exact, on erroneous uses (`a56an.mcnemar`).
- **x_F:** mean over K of C_FA = (comparator passes + flips) per anneal, over production's C_AP = L + F per anneal, on the same batches.

## 7. Analysis
Per point:
- **Primary, scope "all":** fixed first-accept over production (X3P).
  - Terms as A5.5 §9: *Antiphase leads* if the CI lower bound > 1; *SA leads* if the upper bound < 1; otherwise *no detected difference*.
- **Quantization, scope "matched":** fixed first-accept over floating first-accept.
  - *Fixed worse* if the lower bound > 1; *fixed better* if the upper bound < 1; otherwise *no detected difference*.
- **Also reported:**
  - fixed first-accept over floating Antiphase (i);
  - on matched batches, the same ratios with the floating pick, and production over floating Antiphase, as checks against A5.5/A5.8;
  - x_F on "all" and on "matched";
  - coefficients beyond 14 bits (the RTL's width) or 16 bits;
  - the host check.

## 8. Predictions (before any held-out batch)
| Prediction | p |
|---|---|
| Quantization, no detected difference, P1 / P2 / P4 (each) | .85 / .85 / .80 |
| Fixed/floating first-accept point estimate within [0.85, 1.15], each point | .70 |
| Primary P1: SA leads | .90 |
| Primary P2: no detected difference / SA leads / Antiphase leads | .40 / .30 / .30 |
| Primary P4: SA leads / no detected difference / Antiphase leads | .70 / .28 / .02 |
| x_F ≤ 1.10 at every point | .95 |
| Fixed x_F within ±5% of the floating pick's (0.86 / 0.65 / 0.56) | .80 |
| No coefficient beyond 14 bits in any batch | .90 |
| Host check: under 0.5% of uses differ from saved X3P | .80 |

## 9. Decision rule: what each outcome lets the text say (fixed now)
Nothing enters the paper without the author's go. If something enters, it enters with its verdict, whatever that is.

| Outcome (primary) | What the text may say | What it may not say |
|---|---|---|
| P1 and P4 *SA leads*, P2 not *Antiphase leads* | "In fixed point (the first-accept RTL's arithmetic, in the production model's wrapper), first-accept SA keeps its lead over fixed-point Antiphase at 16 and 64 users [and ties / leads at 32]." The Conclusion's "Pending its fixed-point BER and a 32-user re-test" may become "Pending a 32-user re-test against re-tuned Antiphase". | That the 32-user re-test (re-tuned Antiphase, D9) is settled. Throughput, area or energy from this run. |
| P2 *SA leads* | Only together with the row above: "in fixed point it also leads at 32 users against the production schedule (one point, N_s 8, exploratory)". | That it beats re-tuned Antiphase at 32 users. |
| P1 or P4 *no detected difference* | That point's first-accept win is stated as floating point, and the fixed-point result is given beside it. | "Beats Antiphase" at that point without "in floating point". |
| Any *Antiphase leads* | Must be reported wherever the first-accept claim for that point appears (abstract, Results, Conclusion), with its size. | The unqualified first-accept win at that point. |

**Quantization:**
- *Fixed worse* at a point: "fixed point raises first-accept's BER by r [lo, hi]×".
- Otherwise: "no detected loss from fixed point".

**Budget:** x_F > 1.10 at a point means the result is reported "at x_F = …", not "at no more modeled cycles".

**Coefficients beyond 14 bits:** reported with their count. The model computes them exactly, but the RTL would need saturation, so "the RTL's arithmetic" then holds only for the rest.

**Host check:** reported only.

## 10. Files
- `src/`, `build/fa_fx.cubin` (+ ptxas log), `x3model/` (production model sources, `libape.so` built on hostA), `refs/`, `gate/`, `probe/`, `results/`, `hostcheck/`, `logs/`.
- `SHA256SUMS_A513.txt` freezes this protocol, the code, the cubin and the references before launch.
