# PROTOCOL A5.17: k-row commit re-cost of Chord (cycle model only)

Written and frozen 11 Nov 2026, before any A5.17 counter run. The go was the user's "Start both" (11 Nov 2026, about 05:00 CET), approving `../PLAN_A517_A518_20261111.md`. The paper does not change without the user.

## 1. Question
Blind reviewers say the answer "flipping all does not pay" comes from charging one cycle per flip. With a k-row commit unit, Chord commits up to k of a round's accepted flips per cycle.

Does Arpeggio still fit within Chord's cycles, and therefore keep its printed BER comparisons, when Chord gets:
- a k-row commit (k = 2, 4, ∞), or
- free commits (only tests charged)?

## 2. Why BER does not change
Chord decides all flips of a round on one field snapshot. Committing them k at a time reaches the same state as committing them one by one. **Chord's decisions and BER are unchanged; only its cycle count changes.**
- No new BER run is needed for Chord.
- Arpeggio's cycles do not change: first-accept flips one spin, then re-tests.

## 3. Cost model
Per anneal, with m_r flips in round r and L rounds (L_K = 256 K for these runs; checked from steps/anneals):
- C_Ch,1 = L + F (today);
- C_Ch,k = L + Σ_r ⌈m_r / k⌉;
- C_Ch,∞ = L + #{r : m_r ≥ 1};
- C_Ch,0 = L (free commits; the lower bound for any commit hardware).

**Convention, as in every A5.x analysis:** compute the per-K ratio, then take the plain mean over K = 1, 2, 3.
- Every printed x is x = mean_K c_K / ref_K. For P1/P2, ref_K = L_K (1 + φ_K), with φ from `tuned_a52.json` (seed-1000 calibration). At 64 users, ref_K is A5.8's `ref_cost` (seed 1000, job tunea).
- Re-costed: x′_k = mean_K c_K / ref_k,K, with ref_k,K measured on **the same calibration draws** that define ref_K.

## 4. Comparisons (every Arpeggio-vs-Chord BER comparison printed in main.tex 07c4cb36eeb8)
Arpeggio's per-K held-out x come from `results_a514/analysis_a514_final_20261111.json`.

| Key | Comparison | Arpeggio x (per K) | Chord reference |
|---|---|---|---|
| Q1 | P1, B = 1 pick | W1 / A516 float: 0.687 / 0.892 / 0.973 (0.851) | default (φ x16) |
| Q2 | P2, B = 1 pick | 0.550 / 0.692 / 0.712 (0.651) | default (φ x32) |
| Q3 | 64 users | 0.408 / 0.451 / 0.810 (0.556) | default (A5.8 ref_cost) |
| Q4 | P2, S = 76, "at no more cycles" vs re-tuned Chord | A515 Astar: 0.878 / 1.196 / 1.302 (1.125) | re-tuned Chord C1: 1.017 / 1.300 / 1.231 (1.183) |
| Q5 | fixed point P1/P2/64 users | A516 fixed_x (within 0.002 of Q1–Q3) | default |

- **Q4** is compared as x_A′ ≤ x_C1′, both re-costed with C1's own per-round counts. Re-tuned Chord's counts come from its seed-1000 calibration entry (`a55/flips.json`, `abl_ape_0.2_0.2_0.2_rand_8`).
- **Not re-costed:** the routed time and energy ratios. They use RTL cycles of built engines; a k-row Chord engine does not exist.

## 5. Stages
- **S1, free commits (C_Ch,0 = L).** A deterministic transform of stored numbers: x′_0 = mean_K x_K · ref_K / L_K. For Q4, the comparison is against re-tuned Chord's mean_K L_K / L_K = 1.
  - *Disclosure:* I read the inputs (φ, ref_cost, per-K x) before freezing, to design S2. S1 has no free choice beyond §3's convention. **No prediction is recorded for S1.**
- **S2, k = 2, 4, ∞.**
  - **Code:** a counter-only copy of each Chord kernel adds, per round and per anneal, m_r = the number of flips in that round, and accumulates Σ⌈m_r/k⌉ and a histogram (m = 0, 1, 2, 3, ≥4). The kernels are `apx.anechoic_classes` (P1/P2/P3 φ), `apx55.ape_k` (re-tuned C1) and `a56lib.ape` (64 users).
  - **Runs:** each calibration is rerun exactly: `calib_flips.py` (x16, x32, q32); the C1 entry of `calib_flips_a55.py`; A5.8's tunea REF job (`a56_128_0.3_0.3_0.4_0_alt_8`, seed 1000, 8 batches of 500).
  - **Gates (all must pass before any S2 number is used):**
    - (G1) on test instances, the patched kernel's best_s equals the original's bit for bit, from identically seeded generators;
    - (G2) the k = 1 sums equal the stored flips, steps and anneals exactly: a5_flip_phi raw, flips.json C1 entry, A5.8 ref_cost to 1e-9;
    - (G3) the counters draw no random numbers.
  - **Host:** hostB, GPUs idle-with-yield, untimed, at most 4 CPU threads (A5.18 has CPU priority).
- **S3, only where x′_k > the reference** (Arpeggio over k-row Chord's budget). Re-pick Arpeggio within the new budget and rerun held-out. Its rule will be frozen as an amendment before any S3 result; it is not run without that amendment.

## 6. Decision terms (per comparison and k)
- **Fits at k:** Arpeggio's re-costed held-out x′_k ≤ 1 (Q4: ≤ C1's x′_k). The printed BER comparison stands unchanged under a k-row commit.
- **Over budget at k:** x′_k > 1. The printed comparison does not hold at k; S3 may test a re-pick.
- **Also reported:** the per-round flip histogram per point and K (the fraction of rounds with 0, 1 and ≥2 flips).

## 7. Predictions (S2 only; frozen)
| Comparison | k | Prediction | Probability |
|---|---|---|---|
| Q1, Q2, Q3 | ∞ | fit | 0.8 |
| Q1, Q2, Q3 | 2 | fit | 0.9 |
| Q4 | ∞ | fits | 0.5 |
| P1–P3 default Chord | any | fewer than 15% of rounds have ≥2 flips | 0.7 |

## 8. Outcome → text (author's call)
- **All fit at k = ∞:** "even when one cycle commits any number of flips" can replace "multi-row commits are untested". The scope "at one cycle per flip" can widen.
- **Some are over budget:** report point by point and keep the scope.
- **Free-commit (S1) results** are printed as the bound, whatever they are.
