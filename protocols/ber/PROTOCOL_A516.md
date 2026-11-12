# PROTOCOL A5.16: why fixed-point Arpeggio lost 1.58× at P1 (stage 1 confirmatory, stage 2 exploratory)

**Status:** draft 10 Nov 2026, 06:20 CET. Frozen with `results/a514/SHA256SUMS_A514_A516.txt` on hostB, before any new batch.
**Go:** author, 10 Nov 2026: "<instruction>" and "<instruction>".
**Paper:** unchanged without the author's go. The Limitations now say: "Fixed-point models pass if their paired fixed/float BER ratio has a 95% CI upper bound below 1.10: … Arpeggio's only at 64 users (2.32/1.13/1.07)".

## 1. Questions
- **Q1 (stage 1, primary).** A5.13 measured the fixed/float ratio on only 28,000 uses at P1 (1.575 [1.101, 2.317]) and 43,000 at P2 (0.904 [0.719, 1.128]), because floating Arpeggio existed only on those batches. On all of A5.13's fixed-point batches, what are the fixed/float ratios at P1 (400,000 uses) and P2 (300,000 uses)? P4 already has 300,000 (0.978 [0.892, 1.075]).
- **Q2 (stage 2, exploratory).** Does a finer fixed-point scale (Q = 2^16 instead of 2^12) remove any loss that stage 1 confirms?
  - A5.13 named three candidates: integer G/h at Q = 4096, T rounding (410/4096), and the different random streams.
  - Note: the A5.13 kernel draws full 32-bit uniforms (`philox_w`), so there is no RNG-width factor to test.
  - Q = 2^16 refines G, h, T and q together. A change of the Philox key is the stream control.

## 2. Stage 1: float extension (same arms as A5.13's quantization check)
- **Float:** `abl_far_64_0.1_0.1_0_rand_32` at P1 (seed 102, B 2,000) and `abl_far_32_0.1_0.1_0_rand_8` at P2 (seed 102, B 1,000).
- Batches P1 14–199 and P2 43–299 are new; P1 0–13 and P2 0–42 are A5.5's saved batches. Run by `src/trace_a514.py` on hostB.
- G2 (A5.14) showed that this worker reproduces saved batch 0 of both picks bit for bit.
- **Fixed:** A5.13's batches, unchanged: hostA `a513/results/x16|x32/fafx_*`, copied to hostB `results/a514/a513_fixed/`; local copy `results_a513_fixed/`.
- These new float batches double as A5.14's W = 1 arms at P1 and P2.

## 3. Stage 2: fixed-point variants (P1, hostB)
`src/run_a516.py` is run_a513.py (A5.13's x3_prod wrapper with fa_fx.cu) with two options:
- `--qbits` (12 = A5.13). It sets Q in anefx.to_fixed's arithmetic, with J kept as int32 (Q = 2^16 overflows int16), and in fa_schedule.
- `--key-tag` (0xA513 = A5.13).

The kernel is fa_fx.cu, unchanged, built for sm_120 (`build/fa_fx_sm120.cubin`).

| Variant | qbits | key tag | Role |
|---|---|---|---|
| V0 | 12 | 0xA513 | A5.13 rerun on hostB (host check against hostA) |
| V1 | 16 | 0xA513 | finer scale |
| V2 | 12 | 0xA516 | stream control |

- Draws: P1 seed 102, batches 0–199 of 2,000 uses (the stage-1 batches).
- Coefficient check: no |G| or |h| beyond 2^17 at V1; the int32 field bound (|w| < 2^31) is checked by the maximum coefficient times D and P.

## 4. Gates (before the freeze; stage 2 only)
- **G4 (as run, 10 Nov 06:09 CET; `results/a514/gate_G4.json`):** run_a516.py at V0 with the sm_120 cubin, batch 0 against A5.13's hostA batch 0.
  - P4: identical per-use bit errors and x̂.
  - P2: 1 of 1,000 uses differs. P1: 2 of 2,000.
  - The wrapper's counters (sub-problems, flips) differ slightly at all three points. The x3 wrapper runs on the CPU, and hostB's float rounding changes a few search regions; A5.13 measured this host effect at 0.07–0.21% of uses.
  - **Disclosed change to the draft gate:** the draft asked for bit identity at P2 too. It was relaxed, before the freeze, to "≤ 0.5% of uses differ at P1/P2", because this is the known host effect, not an outcome.
  - **Consequence for stage 2:** V0, V1 and V2 all run on hostB and are compared with each other and with hostB's float batches. Stage 1 pairs hostA's fixed batches with hostB's float batches, as A5.13 did.
  - At Q = 4096, run_a516's to_fixed_q is anefx.to_fixed itself (int16 J). The int32 path is used only at qbits > 12.

## 5. Estimators
As A5.15 section 6: ratios of summed bit errors over paired uses, `a56an.boot_ratio` (4,000, seed 12345), exact McNemar.
- **Terms:** "fixed worse" if the lower bound > 1, "fixed better" if the upper bound < 1, otherwise "no detected difference".
- **The paper's pass check:** upper bound < 1.10.

## 6. Analysis
- **Stage 1 (primary):** fixed/float at P1 over batches 0–199 and at P2 over 0–299. Also reported: batches 0–13 / 0–42 alone (A5.13's numbers, as a reproduction) and batches 14+ / 43+ alone.
- **Stage 2:** V1/V0, V2/V0, V0/float, V1/float, V2/float at P1 over the batches done by all.
- **"Q explains the P1 loss"** if all three hold:
  - stage 1 has P1 "fixed worse";
  - V1/V0 upper bound < 1;
  - V1/float upper bound < 1.10.
- **Confirmation:** if Q explains, V1 runs at P2 (0–299) and P4 (seed 344, 0–299) before the cut. The fix passes where V1/float upper bound < 1.10.
- **Cost of the fix** (reported, no synthesis): coefficient width (bits of max |G|, |h|) and field width at Q = 2^16 against Q = 2^12.

## 7. Time cut
11 Nov 2026, 20:00 CET. The analysis uses completed batches common to the compared arms.

## 8. Predictions
- Stage 1 P1 fixed/float about 1.15–1.25, with the upper bound above 1.10: p = .6. Reasoning: fixed Arpeggio over floating Chord on 396,000 uses was 0.530, against floating Arpeggio over floating Chord 0.441 on 28,000.
- P2 passes (upper < 1.10): p = .6.
- V2/V0: no detected difference, p = .9.
- V1/V0 upper < 1: p = .25.

## 9. Outcome → text (frozen)
| Outcome | What the text may say |
|---|---|
| Stage 1 P1 and P2 both pass (upper < 1.10) | Limitations: "…, Arpeggio's at P1/P2/64 users (hi1/hi2/1.07, 400k/300k/300k uses)". The 2.32/1.13 bounds were small-sample. The "1.58×" clause goes. |
| P1 fails, P2 passes | "Arpeggio's at P2/64 users but not at P1 (hi1)". With the new interval, the A5.13 numbers are replaced. |
| P1 "fixed worse" and Q explains (stage 2) | Add: "a 2^16 scale removes it (V1/float r [lo, hi]) at +4 coefficient bits". Only where confirmed at P2/P4 may the text say the fix passes there. |
| P1 "fixed worse", Q does not explain | "cause not found (scale and stream tested)". The limitation stays. |
| P2 fails | Stated as is. |

May not say: any synthesis, area or energy for the fix; any timing.

## 10. Compute and files
- hostB GPU0–3, as A5.15 section 10. Stage 2 runs at most two run_a516 processes with 4 threads each, so with the float workers the total stays ≤ 24 cores.
- Outputs:
  - stage 1: `results/a514/a516f/<shape>/<method>/snr_<snr>/`;
  - stage 2: `results/a514/a516x/<tag>/<method>/snr_<snr>/`.
