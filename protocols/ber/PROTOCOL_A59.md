# PROTOCOL A5.9: RTL cycles of first-accept SA and Antiphase at one and four contexts (exploratory, cycles only)

- **Author's go:** 7 Nov 2026, "Run it". It answered the question "Run the RTL cycle check at one and four contexts?" asked in the coordinating session.
- **Written:** 7 Nov 2026, about 01:20 CET. All sections, including the predictions, were written before any A5.9 code ran. Hash: SHA-256 in `rtl_a59/SHA256SUMS_A59.txt` on hostB.
- **Scope:** RTL cycle counts only. No BER run, no timing, area or energy, and no kit data. A5.8 is untouched (separate folder, CPU only here).

## 1. Question
At the A5.5 B = 1 first-accept picks, do RTL cycles change the verdict that first-accept SA (rule (2), same D comparators) fits within Antiphase's cycles? The check runs at one context (A = 1) and at four contexts with every context filled (A = 4, as in Table IV: "Four queued contexts reuse fixed G, h").

## 2. What A5.5 already settles
- First-accept at A = 1: RTL cycles = 3·tests + 2·F exactly (A5.5 §8, 120 anneals × 4 runs, offset 0).
- Latency model of A5.5 §3 (first-accept 3·tests + 2·F against Antiphase 3·L + F + n₁, n₁ in [0, L]). At the B = 1 picks it gives a mean over K of P1 0.845–0.918 and P2 0.640–0.734 (`results/a55/analysis.json`, `x_lat_n1_*`). So A = 1 is expected to keep both picks within budget. The Antiphase side of that model was never compared with RTL cycles.
- The A5.5 A = 4 runs used R = 2 anneals per sub-problem, so at most two contexts were busy. Their cycles are not the Table IV operating point.

## 3. Configurations (fixed)
| Point | Lanes D | Anneals per sub-problem R | Antiphase (i) | First-accept B = 1 pick |
|---|---|---|---|---|
| P1 16×16 16-QAM 20 dB | 32 | 32 (Ns) | par, 128 sweeps × P half-steps, T 0.3 constant, q 0.4, rand | `abl_far_64_0.1_0.1_0_rand_32`: S 64, T 0.1 constant, q 0, rand |
| P2 32×32 16-QAM 22 dB | 64 | 8 (Ns) | the same schedule (apx.MA) | `abl_far_32_0.1_0.1_0_rand_8`: S 32, T 0.1 constant, q 0, rand |

- **Engines:** `ape_engine.sv` v1.4 (SHA `67367973…`) for (i); `ape_engine_fa.sv` (SHA `ada30595…`) for first-accept; both unchanged from `rtl_a55/src`. `APE_PHILOX`, Verilator, A = 1 and A = 4, D = 32 (P1) and D = 64 (P2).
- **Stimulus:** dev seed 9600 only; 20 real MDI sub-problems per K = 1, 2, 3.
  - P1 reuses `rtl_a55/capture_9600.pt`.
  - P2 is captured the same way (`capture_a59.py`: x32 shape, 22 dB, Ns 8, the same capture solver), on hostB GPU0 or GPU1 through `env_hostb_a56.sh`.
  - No held-out draw is read.
- **Harness changes (testbench and reference only, never the engines):**
  - R is a parameter.
  - D is taken from the stimulus.
  - The 'par' reference runs 128 × P half-steps (the paper's L = 128·P; A5.5's v14 baseline ran 128).
  - The testbench also logs each accepted command (op, cycle).
  - Before any A5.9 configuration is counted, the A5.5 behavioural checks must pass on every run.

## 4. Metric
- **Cycles of a K block:** from the first accepted LOAD_ROW of the block to the block's last output beat, plus one. This includes G/h loading and excludes schedule-table loading, as the paper counts ASIC cycles. Per anneal = block cycles / (20·R).
- **x_RTL,A** = mean over K of first-accept cycles per anneal / Antiphase cycles per anneal, at A = 1 and A = 4.
- **Model on the same stimulus:** x_F,stim = mean over K of (tests + F)_FA / (L + F)_AP, from the reference's own counts.
- **Correction:** c_A = x_RTL,A / x_F,stim.
- **Held-out estimate:** x̂_A = x_F,held × c_A, with x_F,held = 0.862 (P1) and 0.649 (P2) from A5.5.
- Every K is reported, together with RTL cycles over the model per engine.

## 5. Decision rule and what each outcome lets the text say (fixed now)
1. **x̂_A ≤ 1 at both points and both A.** The picks stay within Antiphase's cycles in RTL. The A5.5 verdict (SA leads at P1, ties at P2) holds in cycles at one and four contexts.
   - Text: unchanged. The author may choose "a cost model confirmed in RTL simulation at one and four contexts" if it is line-neutral.
   - Advice: no GF22 first-accept work for the deadline, since any remaining difference is per-cycle cost, expected small (`ape_engine_fa.sv` is v1.4 plus a lane mask and a re-test return).
2. **x̂_A > 1 at some point or A.** That pick exceeds Antiphase's RTL cycles there, and the B = 1 verdict at that point is not established under RTL cycles.
   - Text: no change.
   - Next step: re-costing the stage-A cells with an RTL-fitted cost, re-picking and running the held-out BER would need its own protocol. A GF22 comparison would then be informative.
3. **Within 0.97–1.03 at a point:** reported as "at the budget edge". Rule 2 applies for "not established".
- In every outcome, no claim about time, area or energy, and no "Antiphase beats SA" from cycles alone.
- A failed behavioural check stops the run. The cause is reported and no cycle number is used.

## 6. Predictions (mine, before any A5.9 code ran)
| Claim | P |
|---|---|
| All behavioural checks pass, including D = 64 | .85 |
| A = 1: x_RTL,1 on the stimulus lies within the A5.5 latency bounds (n₁ = 0 to L) | .8 |
| A = 4: c_4 within 0.85–1.15 at both points | .65 |
| P1 x̂_4 ≤ 1 | .75 |
| P2 x̂_4 ≤ 1 | .95 |
| P1 x̂_1 ≤ 1, P2 x̂_1 ≤ 1 | .9, .97 |
| Outcome 1 overall | .7 |

Reasoning: in A5.5's two-context runs, RTL over the model was 1.42–1.80 for first-accept and about 1.5 for Antiphase. The pick at P1 is test-heavy (F/tests 0.2–0.5), the worst case for the decision-port latency, so P1 has the thinner margin (1/0.862 = 1.16).

## 7. Compute
- hostB CPU only, `nice -n 19`, at most 8 simulator processes, Verilator `-j 4`.
- One short GPU capture for P2 on GPU0 or GPU1 (UUID-checked by `env_hostb_a56.sh`), untimed.
- Everything is under `<SCRATCH>/ap_ber_20261024/rtl_a59/`. No other user's process is touched.
