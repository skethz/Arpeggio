# PROTOCOL A5.14: commit width W (exploratory)

**Status:** draft 10 Nov 2026, 06:15 CET. Frozen when `results/a514/SHA256SUMS_A514_A516.txt` is written on hostB, before any held-out batch of a W > 1 arm.
**Go:** author, 10 Nov 2026: "<instruction>" and "<instruction>".
**Paper:** unchanged. Nothing from this run enters main.tex without the author's go. Because a W > 1 win would touch the title claim ("Flip in Sequence"), any such outcome goes to the author first, and the author decides the wording.

## 1. Question
Reviewers asked whether committing a few flips per test pays (r2: HW, MIMO top item).

At P1 (16×16, 20 dB, N_s 32), P2 (32×32, 22 dB, N_s 8) and P4 (64×64, 22 dB, N_s 8), all 16-QAM: does committing the first W ∈ {2, 4} accepted spins per test, at no more modeled cycles than Arpeggio, change BER relative to Arpeggio (W = 1)?

## 2. Policy (`src/apx514.py`, `fa_seq_w`)
- One test cycle tests every remaining lane of one copy bank on the current fields, with rule (2) and one random number per spin per sweep, as Arpeggio.
- The first min(W, accepted) accepted lanes in scan order are committed one after another. Each commit is a field-update cycle, and its energy change is taken from the fields at its commit.
- Lanes after the first commit therefore act on a stale test, as parallel flips do. The lanes after the last committed lane are re-tested.
- W = 1 is Arpeggio: `fa_seq_w` sends W = 1 to `apx55.fa_seq` itself.
- **Cycles per anneal:** tests + flips, with tests = S P + commit groups − groups ending on a pass's last lane.
- **Assumption, favouring W > 1:** the find-first-W pick is charged nothing.

## 3. Arms and S_W (fixed before any held-out batch)
- **W = 1:** the paper's Arpeggio picks:
  - P1 `abl_far_64_0.1_0.1_0_rand_32` (A5.5);
  - P2 `abl_far_32_0.1_0.1_0_rand_8` (A5.5);
  - P4 `abl_far_64_0.1_0.1_0_bal_8` (A5.8).
- **W = 2, 4:** `abl_faw_<W>_<S_W>_<T0>_<T1>_<q>_<start>_<Ns>`, with the pick's T0, T1, q, start and N_s. T is not re-tuned (stated as a limitation).
- **Calibration:** `src/calib_a514.py`, tuning seed 1000, batch index 50, solver seed 1000 (A5.5 section 7). P1 1,000 uses, P2 500, P4 500.
  - The cost reference is A5.5's L_K (1 + φ_K) at P1/P2 and A5.8's ref_cost at P4.
  - The pick's x is recalibrated on the same batch. At P1 it reproduces A5.5's 0.8620 exactly.
- **Rule:** S_W is the largest S in {48, 52, …, 96} (P1, P4) or {24, 28, …, 56} (P2) with x(W, S) ≤ x(pick). If the grid's top fits, it extends upward in steps of 4; if its bottom does not, downward.
- Values are recorded in section 11 before the freeze.

## 4. Gates (before the freeze)
- **G1:** `fa_seq_w(force=True)` at W = 1 equals `apx55.fa_seq` rule 'r' bit for bit, in best spins and every counter. 36 cases: P1/P2/P4 × K 1–3 × both starts × two (S, T, q).
- **G3:** at W = 2 and 4, `fa_seq_w` equals `ref_w` bit for bit. `ref_w` is a per-anneal loop written from the definition, with the same random-number calls. The tracked energy must match a recomputation (|ΔE| < 1e-3), and the tests identity must hold.
- **G2:** `trace_a514.py` reproduces saved batch 0 of each W = 1 pick bit for bit (P1/P2 seed 102, P4 seed 344).
- **Result:** G1/G3 PASS (`results/a514/gate_G1G3.json`); G2 PASS 10 Nov 06:06 CET.

## 5. Held-out draws
No W > 1 setting has ever run on these seeds, and S_W comes from seed 1000 only. So the picks' held-out seeds and A5.13's batch sets are held-out for W:
- P1: seed 102, batches 0–199 of 2,000 (400,000 uses);
- P2: seed 102, batches 0–299 of 1,000 (300,000 uses);
- P4: seed 344, batches 0–599 of 500 (300,000 uses).

**W = 1 data:**
- P4: A5.8's saved batches (held0–held11, all 600).
- P1: saved batches 0–13 (A5.5) plus 14–199.
- P2: saved batches 0–42 plus 43–299.
- The new W = 1 batches are A5.16 stage 1's float extension (same worker, same method name, so the same streams).

**Queue:** A5.15 first; A5.16 stage 1; A5.14 P1 and P2 (W = 2 and 4 interleaved); P4 W = 2; P4 W = 4 last.

**Time cut:** 11 Nov 2026, 20:00 CET. Each comparison uses the batch indices completed by both of its arms.

## 6. Estimators
As A5.15 section 6: ratio W/W1 of summed bit errors over paired uses, `a56an.boot_ratio` (4,000, seed 12345), exact McNemar. Terms: "W helps" if the upper bound < 1, "W hurts" if the lower bound > 1, otherwise "no detected difference".

## 7. Decision (per W)
- **Helps:** at least 2 of the 3 points have "W helps", and no point has "W hurts".
- **Hurts:** at least 2 of 3 points have "W hurts", and none has "W helps".
- **Mixed or unresolved:** otherwise, reported point by point.
- If P4 is missing at the cut, the rule uses P1 and P2, and both must agree.
- Also reported: held-out x per arm and K; flips, commit groups and tests per anneal.

## 8. Predictions
At matched cycles W = 2 gets fewer sweeps (calibration: W = 2 costs more per sweep at P1, because stale commits add flips).
- W = 2 hurts or does not differ at every point: p = .75.
- W = 4 hurts at ≥ 2 points: p = .6.
- Either W helps: p = .1.

## 9. Outcome → text (frozen)
| Outcome | What the text may say |
|---|---|
| Both W hurt | V-B (or Table I): "Committing the first 2 or 4 accepted flips per test, at no more cycles, raises BER (W = 2: r [lo, hi] … at P1/P2/P4; exploratory)." It supports "flip in sequence". The intro may say "flipping more than one per test does not pay". |
| One hurts, other unresolved or mixed | The same sentence, for the W that hurts; the other is stated as not detected. |
| Unresolved or mixed | "Committing W = 2 or 4 flips per test shows no detected BER difference at equal cycles (…)". No claim that one flip per test is necessary. |
| Either W helps | Reported to the author before any text. The text may say only "committing W flips per test lowers BER at … (exploratory)". The title, RQ and "flip in sequence" change only by the author's decision. |

Always stated with any use: T not re-tuned for W; the find-first-W pick uncharged; float model, untimed.

## 10. Compute and files
As A5.15 section 10. Outputs: `results/a514/a514/<shape>/<method>/snr_<snr>/`. W = 1 extension batches: `results/a514/a516f/`.

## 11. Calibration record (filled before the freeze)
(filled below)
