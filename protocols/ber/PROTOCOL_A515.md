# PROTOCOL A5.15: 32-user re-test of Arpeggio against re-tuned Chord at equal modeled cycles (confirmatory)

**Status:** draft 10 Nov 2026, 06:10 CET. Frozen when `results/a514/SHA256SUMS_A514_A516.txt` is written on hostB, before any held-out batch of seed 2027.
**Go:** author, 10 Nov 2026: "<instruction>" (all Tier 1/2 experiments of `<PROJECT>/work/review_blind_20261110_r2/EXPERIMENT_PLAN.md` will run) and "<instruction>" (hostB GPU0–3).
**Paper:** unchanged. Nothing from this run enters main.tex without the author's go.

## 1. Questions
- **Q1 (primary).** At P2 (32×32 16-QAM, 22 dB, N_s = 8), given re-tuned Chord's modeled cycles, does Arpeggio have a different BER from re-tuned Chord?
  - Re-tuned Chord: `abl_ape_0.2_0.2_0.2_rand_8` (A5.5 pick, T0 = T1 = 0.2, q = 0.2), x_F = 1.12 of default Chord (A5.5 calibration 1.1204).
  - Arpeggio: rule (2), T = 0.1 constant, q = 0, random start, as the A5.5 P2 picks at B = 1 (S = 32) and B = 2–3 (S = 128); S = S* (section 3).
- **Q2 (secondary).** The paper's Arpeggio at P2 (`abl_far_32_0.1_0.1_0_rand_8`, x_F 0.649) against default Chord (`mdiane8`): the re-test of "unresolved at 32".
- **Q3 (secondary).** Re-tuned Chord against default Chord: a second held-out estimate of the re-tune (seed 102 gave 0.88 [0.68, 1.14]).
- **Q4 (secondary).** Arpeggio at S* against default Chord.

## 2. Arms (float, same draws)
| Arm | Method | Note |
|---|---|---|
| C0 | `mdiane8` | default Chord, as Table III |
| C1 | `abl_ape_0.2_0.2_0.2_rand_8` | re-tuned Chord, frozen since A5.5 |
| A* | `abl_far_<S*>_0.1_0.1_0_rand_8` | Arpeggio at re-tuned Chord's cycles |
| A32 | `abl_far_32_0.1_0.1_0_rand_8` | the paper's Arpeggio at P2 |

The arms run through `src/trace_a514.py` (trace_a56.py with the x64 shape and apx514 registered). Draws: `apx.draw(2027, 22, bi, 1000, 32, 16)`; solver streams as the runner (draw seed + 7919 + mhash(method)).

## 3. S* (fixed before any held-out batch)
- Calibration: tuning seed 1000, batch index 50, 500 uses, solver seed 1000, as A5.5 section 7 (`src/calib_a514.py`).
- Cost: x = mean over K of cycles per anneal over default Chord's L_K (1 + φ_K) (φ from tuned_a52.json). Arpeggio's cycles are tests + flips; Chord's are L_K + flips.
- **Rule:** S* is the largest S in {56, 60, …, 88} with x(S) ≤ x(C1), both from the same calibration batch. If x(88) ≤ x(C1), the grid extends upward in steps of 4; if x(56) > x(C1), downward.
- The calibrated values and S* are recorded in section 11 before the freeze. The held-out x of every arm is reported (descriptive).

## 4. Gates (before the freeze)
- **G2 replay:** `trace_a514.py` reproduces batch 0 of seed 102 bit for bit (bit errors and erroneous x̂) for C0 (`results/abl/x32/mdiane8`), C1 and A32 (`results/a55/abl/x32/...`).
- **G1/G3** (A5.14's code) must pass, since the worker loads apx514.

## 5. Held-out run
- **Seed 2027:** never used on hostB or hostA (checked 10 Nov over every done.json).
- Batches 0–299 of 1,000 uses: 300,000 paired uses per arm, fixed in advance. No early stopping.
- Chunks of 20 batches. The four arms are interleaved chunk by chunk, so they progress together.
- **Time cut:** 11 Nov 2026, 20:00 CET. If not complete by then, the analysis uses the batch indices completed by all four arms. Which batches complete depends on the queue, not on results.

## 6. Estimators
- BER ratio = Σ bit errors (arm) / Σ bit errors (reference), over the same uses.
- 95% CI: paired bootstrap over uses, `a56an.boot_ratio` (4,000 replicates, seed 12345).
- Exact McNemar on uses with an error in exactly one arm (`a56an.mcnemar`).
- **Terms:** "Arpeggio leads" if the upper bound < 1; "Chord leads" if the lower bound > 1; otherwise "no detected difference".
- Reported for each arm: uses, bit errors, erroneous uses, BER, held-out x per K.

## 7. Analysis
- **Primary:** A*/C1. Secondary: A32/C0, C1/C0, A*/C0, A*/A32.
- The primary is the only confirmatory comparison. The secondaries are reported as such, without correction.
- A check, not a decision: if A*'s held-out x exceeds C1's by more than 2%, that is reported next to the primary.

## 8. Predictions (written before the run)
- A*/C1 about 0.6 (interpolating seed-102 BER between S = 32 and 128). "Arpeggio leads": p = .80.
- A32/C0 about 1.0, "no detected difference": p = .55.
- C1/C0 about 0.9, "no detected difference": p = .55.
- S* in 68–80: p = .80.

## 9. Outcome → text (frozen)
Every use needs the author's go. "Exploratory" does not apply: this is the pre-registered re-test the Conclusion promises.

| Primary A*/C1 | What the text may say |
|---|---|
| Arpeggio leads | "At 32 users, given re-tuned Chord's cycles (1.12×), Arpeggio has r× [lo, hi] its BER." The abstract may become "beats default Chord at 16 and 64 users and re-tuned Chord at 32, at its cycles". The Conclusion's "Pending a 32-user re-test vs. re-tuned Chord" is removed. It must stay stated that A* uses more cycles than the B = 1 pick. |
| No detected difference | "At 32 users, at re-tuned Chord's cycles, Arpeggio and re-tuned Chord do not differ (r× [lo, hi])." "unresolved at 32" stays; "Pending …" is replaced by the result. |
| Chord leads | "At 32 users, re-tuned Chord leads Arpeggio at equal cycles (r× [lo, hi])." The abstract's "unresolved at 32" becomes a loss to re-tuned Chord. The claim set changes, so the author decides the wording. |

| Secondary | What the text may say |
|---|---|
| A32/C0 Arpeggio leads | "Arpeggio beats default Chord at 16, 32 and 64 users", with this re-test (seed 2027) as the 32-user source and the seed-102 result kept in the record. |
| A32/C0 no detected difference | Unchanged ("unresolved at 32"); the new interval may replace the old one. |
| A32/C0 Chord leads | Must be reported: "default Chord leads the B = 1 Arpeggio at 32 users (r× [lo, hi])". |
| C1/C0 | The new interval may be printed as "on a second held-out seed" next to 0.88 [0.68, 1.14]. |

May not say: any timing, energy or area from these runs (5090, untimed); that A* is the paper's B = 1 pick.

## 10. Compute and files
- hostB GPU0–3 (author, 10 Nov), UUIDs checked by `env_hostb_a514.sh`. Untimed, idle-with-yield (`supervise_a514.sh` stops our workers on a GPU that shows any other compute process), nice 10.
- At most 16 workers with 2 threads each, within the 24-core cap with A5.16's fixed-point processes.
- Outputs: `<SCRATCH>/ap_ber_20261024/results/a514/a515/x32/<method>/snr_22.00/bNNNNN.npz`. Logs: `logs/a514/`.
- Code and inputs hashed in `results/a514/SHA256SUMS_A514_A516.txt`; local copies in `code_a514/`.

## 11. Calibration record (filled before the freeze)
(see section 11 as filled)
