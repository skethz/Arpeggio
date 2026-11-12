# A5.17 amendments

## A1: S3 rule (11 Nov 2026, frozen after S1/S2 and before any S3 run)
**Trigger (§5, S3).** S2 put only Q4 over budget at k = 2, 4 and ∞. Q4 is P2, Arpeggio at S = 76 vs re-tuned Chord C1.
- On A5.15's calibration batch (seed 1000, index 50, 500 uses), C1 costs x_k(C1) = 0.9443 (k = 2), 0.8641 (k = 4) and 0.8215 (k = ∞), against 1.1204 at k = 1. These are the means over K against default Chord's L_K (1 + φ_K). Arpeggio S = 76 costs 1.1251.
- Q1, Q2, Q3 and Q5 fit at every k (§6). Under free commits (S1), Q1 and Q3 are over budget, but free commits are a bound, not hardware, so no S3 run follows from S1.

**Rule.** This is A5.15 §3 with x(C1) replaced by x_k(C1).
- **S*_k** is the largest S on the grid {…, 44, 48, 52, 56, 60, …} with calibration x(S) ≤ x_k(C1), both on the same batch.
- Values for S ≥ 56 come from A5.15 §11 (56: 0.9073, 60: 0.9486, …). Values for S ∈ {40, 44, 48, 52} come from a new `calib_a514.py` run on the same batch, with the method `abl_far_<S>_0.1_0.1_0_rand_8` (T = 0.1 constant, q = 0, rand, as A5.15).
- From A5.15 §11 alone, S*_2 = 56. S*_4 and S*_∞ follow from the new calibration.
- When two k give the same S*, one arm serves both.

**Held-out (as A5.15 §5–6).**
- Seed 2027, batches 0–299 of 1,000 uses, paired with A5.15's stored C1 arm (`results/a514/a515_c*/x32/abl_ape_0.2_0.2_0.2_rand_8`). Same runner (`trace_a514.py`) and draws.
- Primary per k: A*_k / C1, paired bootstrap (4,000 replicates, seed 12345), exact McNemar.
- Terms:
  - "Arpeggio leads": the CI upper bound < 1;
  - "Chord leads": the CI lower bound > 1;
  - otherwise "no detected difference".
- Also reported: A*_k / C0 (default Chord) on the same uses, and every arm's held-out x per K.

**Check, not a decision.** Is the held-out x of A*_k at most x_C1,held × x_k(C1)/x_1(C1), i.e. C1's held-out cost scaled by its calibration k-row ratio?

**Time cut:** 13 Nov 2026 12:00 CET. If the run is not complete, the analysis uses the batch indices completed by every arm.

**Compute:** hostB GPU0–3 (user, 11 Nov: "<instruction>"), untimed, idle-with-yield as `supervise_a514.sh`. The 24-CPU cap holds while A5.18 P&R uses CPUs 0–23: the workers are pinned inside 0–23 at nice 19, one thread each.

**Predictions** (log-linear in S between A5.15's A32/C1 1.39 and A76/C1 0.62):
| k | S* | Expected A*/C1 | "No detected difference" | "Arpeggio leads" |
|---|---|---|---|---|
| 2 | 56 | about 0.9 | p = .55 | p = .35 |
| ∞ | 44–48 | about 1.0–1.1 | p = .6 | |

**Text (author's call):**
- If A*_k does not lead, the 32-user claim "beats re-tuned Chord at no more cycles" holds only at one cycle per flip, and the text must say so.
- If it leads at k = ∞, the claim survives multi-row commits.
