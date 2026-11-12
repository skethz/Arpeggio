# Frozen protocol: Antiphase corrective experiments (items 2, 4, 5 and 8, plus the PIMI regime map)

Written Sat 24 Oct 2026, 10:30 CEST. This was before any held-out run (seeds 101–105) of this protocol. Its SHA-256 is recorded in STATUS.md and copied, together with this file, to both hosts at `<SCRATCH>/ap_ber_20261024/PROTOCOL.md`. The file is not edited after that point; any deviation goes into STATUS.md and RESULTS.md as a dated amendment.

## Already done before this protocol

These steps used development seeds only (9001, 9100, 9200, 9300, 9400, 9500) and the tuning seed (1000):
- **Throughput smoke test.**
- **Unit tests of the new code** (`src/test_apx.py`, ALL PASS on GPU7).
  - `mdi_diag` makes exactly the decisions of `mimo.mdi`.
  - `anechoic_ext` reproduces `mimo.anechoic` bit for bit.
  - Every variant runs on every shape.
- **Device checks.**
  - E0: the CPU draws are bit-identical across hostA (Intel) and hostB (AMD).
  - E1: the integer and fixed-order kernels are bit-identical on the B200 and on all three RTX 5090s, given identical inputs.
- **Observed during development (dev seed 9300), not a result.**
  - A three-level-window synchronous heat-bath on d fails: it never improves on its guess.
  - A random-direction proposal heat-bath works.
  - Both are kept as variants (§4.2).

## 0. Scope and binding decisions
- **User decisions.**
  - No reimplementation of other groups' methods beyond code that already exists: the MDI wrapper, the AHC baseline and the bit-identical PIMI update are reused unchanged.
  - No optimized AHC kernel is built. The "29–148× best implementation" claims are dropped.
  - Competitor headline comparisons use the competitors' own reported numbers with conditions stated (REPORTED_COMPARISON.md).
- **Code.** Existing code is imported read-only from `mimo_ising_20261016/src` (`mimo`, `anefx`, `ahcfx`, `pimi`, `tree`, `mdi_solvers`). New code lives in `ap_ber_20261024/src` (`apx.py`, `runner.py`, `stats_ap.py`, `make_plan.py`, `select_tuned.py`) and only adds wrappers and the new ablation variants.
- **System.** As in the paper:
  - i.i.d. CN(0,1) Rayleigh channels, perfect CSI, Gray unit-energy QPSK and 16-QAM, square N_t = N_r.
  - SNR = N_t·E_s/N_0 per receive antenna (`mimo.make_batch`).
  - Real-valued lift; uncoded BER.

## 1. Hardware and fairness rules
- **Timing.** Every timed number comes from hostA GPU7 (B200, UUID <GPU_UUID>) during a window in which no other process of ours runs on GPU7. It is labelled "non-exclusive host", because hostA's CPUs and other GPUs carry other users' jobs. No time or energy from a 5090 is reported.
- **Error counting** runs on hostB GPU0/1/2 (RTX 5090) and on GPU7 outside timing windows. The CPU tree searches (K-best, sphere decoder) run on hostA's CPUs.
- **hostB limits.** At most 6 workers × 2 threads (≤ 24 cores in total), ≥ 200 GB RAM free, and Vivado is never touched.
- **Implementations.**
  - MDI-AHC uses the AHC CUDA kernel (`ahc_v1`, fp32, fixed order, no FMA) where the couplings fit. Its start states are drawn exactly as `mimo.ahc` draws them, and on identical draws it gave identical bit-error counts to PyTorch AHC (smoke test: 0.000867 both at 16×16 20 dB, 0.00403 both at 32×32 QPSK 12 dB).
  - 16×16 16-QAM AHC jobs need the K = 3 kernel (149 KiB of shared memory), so they run on the B200 only.
  - 32×32 16-QAM AHC uses PyTorch `mimo.ahc`.
  - Antiphase and every ablation variant use the PyTorch float reference (`mimo.anechoic` or `apx` variants), the implementation behind all BER in the paper.
  - The int16 kernel is used only for timing.

## 2. Equivalence of the B200 and the 5090 (before any 5090 result is used)
- **E0 (done).** `apx.draw` builds H, x and noise on a CPU generator seeded by (seed, SNR, batch index). y is formed in float64 and rounded once. The SHA-256 of the draws agrees on both hosts.
- **E1 (done).** For identical saved inputs, the outputs of the ane, AHC (K ≤ 2) and PIMI kernels are bit-identical on the B200 and on the three 5090s: 19/19 cases.
- **E2 (runs first).** The same PyTorch chain jobs run on GPU7 and on a 5090, on the same seed-9100 draws (plan set `equiv`):
  - x16 `mdiane64` at 20 dB, 8,000 uses;
  - x16 `sic` at 22 dB;
  - q32 `mdiane64` at 12 dB, 16,000 uses;
  - x32 `mdiane8` at 22 dB, 2,000 uses;
  - q32 `mdiahck64` at 12 dB.

  **Acceptance.**
  - The PyTorch solver randomness differs by device, so agreement is statistical: |log BER ratio| within the 95 % paired-bootstrap interval of the difference, and McNemar p > 0.01.
  - Deterministic stages (SIC, MMSE) must agree on ≥ 99.9 % of uses (device float rounding).
  - If E2 fails, 5090 results are not used and the jobs move to GPU7.

## 3. Item 2: Table II rerun
**3.1 Data.**
- One held-out seed for every curve: **101**. It was never used before; earlier seeds were 1–13, 41–48, 1000 and the development seeds above.
- Draws depend only on (seed, SNR, batch index), so all methods of a shape see the same channel uses: every comparison is paired. Batch sizes are 2,000 (x16), 1,000 (x32), 4,000 (q16, q32).
- Truncated last batches are prefixes of the full batch draw.
- Solver random numbers come from a per-(method, SNR, batch) CUDA generator.

**3.2 Grids.**
- 0.5 dB steps within ±2 dB of each old crossing, recomputed from the paper's `data/*.jsonl` with the corrected rule of §5.
- Rows whose old 10⁻⁴ crossing lies beyond the old grid (one-stage rows, MMSE-SIC) extend to the old maximum plus 2 dB.
- Exact grids: `make_plan.py` / `grids.json`.
  - **x16 = 16×16 16-QAM.** sic 22.5–28.5 (+31.02); kbest32 17–22.5 (+31.02); sd 16–30; aned64 21–30; mdiahck64 17.5–26; mdiane64 17–23.5; mdiahck8 19.5–27.5; mdiane8 19–26; mmse 31.02.
  - **x32 = 32×32 16-QAM.** sic 23–28; kbest32 19–24.5; aned64 20.5–28; mdiahc128 18–24; mdiane128 16.5–21.5; mdiahc8 21–26.5; mdiane8 18.5–24.5.
  - **q16 = 16×16 QPSK.** sic 11–20; kbest32 9–14.5; sd 8.5–20; ane64ri 10–16.5; mdiahck64 10–16; mdiane64 9–14.5.
  - **q32 = 32×32 QPSK.** sic 11–20; kbest32 9.5–14.5; ane64ri 10–16.5; mdiahck64 11–17; mdiane64 8.5–14.

**3.3 Methods.** Exactly the paper's Table II rows:
- **MMSE-SIC (`sic`):** `mimo.mmse_sic`, real-stream ordering. It is newly added for QPSK.
- **K-best with 32 candidates (`kbest32`):** `tree.kbest2`, sorted QR, real-valued.
- **ML (`sd`):** Schnorr–Euchner sphere decoder, 16×16 only. Node cap 2×10⁶; unfinished instances are re-run with cap 5×10⁷; any still unfinished are counted and flagged "uncertified".
- **One stage, 16-QAM (`aned64`):** dDI K = 1 around MMSE, 64 anneals. x16: S 256, T 0.3, q 0.4. x32: T 0.3→0.2, κ 0.3 (as in the paper).
- **One stage, QPSK (`ane64ri`):** RI formulation. q16: S 128, T 0.7→0.5, q 0.6. q32: S 128, T 0.5→0.4, q 0.4.
- **MDI-AHC (`mdiahck`/`mdiahc`):** Singh et al. 2024 Table I. 16-QAM: λ_mean, R_max 3, S 8. QPSK: DI-MIMO, one stage around MMSE, R_max 1. Rows:
  - published Ns: 64 for x16 and q16/q32, 128 for x32;
  - Ns = 8.
- **Antiphase (`mdiane`):** the same wrapper with the frozen schedule (128 updates per copy, T 0.3, q 0.4, 2K copy phases), at the same Ns.

**3.4 Stopping rule** (per point):
- Run until **≥ 100 erroneous channel uses and ≥ 100 bit errors**, capped at **10⁷ bits**: 156,250 uses for x16 and q32, 78,125 for x32, 312,500 for q16.
- Every batch is saved: the per-use bit-error vector; for each erroneous use its index, ‖y − Hx̂‖² and ‖y − Hx_true‖² (float64) and x̂; and the wrapper diagnostics (§3.5).
- Resumable; existing files are never overwritten.

**3.5 Floor diagnosis.** Applied to every erroneous use of the Ising detectors and K-best.
- **ML error:**
  - x16 / q16: x_ML ≠ x_true, certified by the sphere decoder on the same draws. SD runs on a superset grid and always to at least as many uses, since it has the fewest errors.
  - Elsewhere, a certain ML error is d(x̂) < d(x_true).
- **Search failure:** d(x̂) > d(x_true) and (x16/q16) x_ML = x_true. Search failures split into:
  - **solver failure:** x_true lay inside the box |x − x_g|∞ ≤ 2R_g of a guess that was searched (R_g ≥ 1) at some stage, and the solver did not return it;
  - **radius truncation:** x_true never lay inside a searched box. For the one-stage rows the box is K = 1 around MMSE.
- **Ties and inconsistencies** (d(x̂) ≤ d(x_true) while SD says x_ML = x_true) are counted separately.

**3.6 Table II script.** `analysis/table2.py` regenerates Table II from the saved per-use vectors. For each cell it reports:
- SNR at 10⁻³ and 10⁻⁴, with "≤" where a zero-error bound is used;
- 95 % cluster-bootstrap CIs;
- paired ΔSNR with CIs and McNemar p for these pairs: Antiphase vs MDI-AHC (published Ns and Ns 8), Antiphase vs K-best, Antiphase vs ML (x16/q16), MDI-AHC vs K-best.

A pair whose ΔSNR CI covers 0 is written "matches". Output: `table2.csv`, `table2.json`, `table2.tex` (LaTeX fragment; main.tex is not touched).

## 4. Item 5: ablation inside MDI
**4.1 Points.** Seed **102**, the paper's matched points:
- P1: x16, 20 dB, Ns 32.
- P2: x32, 22 dB, Ns 8.
- P3: q32, 14 dB, Ns 8 (DI-MIMO, one stage, 2 copies).

Same stopping rule as §3.4, with minimum uses 8,000 / 4,000 / 8,000. References on the same draws: MMSE, MMSE-SIC (16-QAM), K-best 32, and MDI-AHC at equal Ns and at AHC's matched Ns (P1 64, P2 32, P3 64).

**4.2 Variants.** Everything else follows (i): same wrapper, schedule, half-step count L = 128·2K, random start and selection.

| Name | Variant |
|---|---|
| (i) `mdiane` | As proposed: copy alternation on, T 0.3, q 0.4, best of trajectory |
| (ii) `abl_noalt` | Alternation off: all copies every half-step |
| (ii′) `abl_noaltq0` | Alternation off and q = 0: plain synchronous SCA |
| (iii) `abl_q0` | q = 0, alternation on |
| (iv) `abl_qdim` | No alternation, per-spin pinning q_{c,m} = q0 + c·2K·G̃_mm, where G̃_mm = (HᵀH)_mm / coefficient scale. (q0, c, T) tuned (§4.3) |
| (v) `abl_dil` | No alternation; each spin may flip at a half-step with probability p = 1/P, P = 2K (random dilution, the same expected number of eligible spins) |
| (vi) `abl_final` | The final state of each anneal instead of the best visited |
| (vii) `abl_ons` | Onsager κT on, κ = 0.3 (milestone D) |
| (viii) `abl_pimi` | PIMI's update (`pimi.run`, bit-identical to the authors' `pbits_im.py`, unchanged) on each MDI delta sub-problem. J symmetrised, h = h0/2, ap_fixed<16,4>; schedule A (16-QAM) or B (QPSK); 128 steps (equal decisions per spin); na trials. Each trial's final state is a candidate (PIMI's output rule), sliced as in PIMI's reconstruction |
| (ix) `abl_sa` | Sequential single-spin Metropolis SA, 128 sweeps (equal decisions per spin), geometric T0→T1 (tuned), best tracked after every D = N/2K spin visits |
| (x) `abl_sym` | **Our own** symbol-level synchronous heat-bath on d (p-dit style). Every dimension proposes a random ±1-level move, accepted with probability 1/(1 + exp((ΔE + 2q)/T)); L synchronous steps. (T, q) tuned |
| (x′) `abl_symw` | The same, but each dimension samples the window {d−2, d, d+2} (heat-bath). (T, q) tuned |

**4.3 Tuning.** Only for variants with free settings, so that they get the tuning privilege Antiphase had. Tuning seed 1000, P1, 4,000 uses per configuration; the chosen setting is reused at P2 and P3, as Antiphase's was.
- **Grids.**
  - (iv): c ∈ {0.25, 0.5, 1, 2} × q0 ∈ {0, 0.4} × T ∈ {0.3, 0.6}.
  - (ix): T0 ∈ {0.3, 0.6, 1.2, 2.4} × T1 ∈ {0.05, 0.15, T0}.
  - (x): T ∈ {0.05, 0.1, 0.2, 0.4} × q ∈ {0, 0.2, 0.4}.
  - (x′): T ∈ {0.1, 0.2, 0.4, 0.8} × q ∈ {0.4, 0.8, 1.6}.
- **Selection** (`select_tuned.py`): fewest bit errors, then fewest erroneous uses, then plan order.

**4.4 Reported per variant and point.**
- BER with its 95 % cluster-bootstrap CI.
- The BER ratio to (i) with a paired-bootstrap CI, and McNemar p against (i).
- Vector error rate and anneals per detection.
- In-chain solver time on GPU7 in a timing window (§4.5).

**4.5 Timing.** Run after the error counting, on GPU7, with no other process of ours on GPU7. Method as in cohort C/D:
- batches of 500 (P1), 250 (P2), 2,000 (P3), on seed-41,000,003-style fresh draws;
- one untimed call, then 3 segments of ≥ 6 s;
- medians of in-chain solver time and chain time per detection.

Coverage:
- every variant in PyTorch;
- the int16 kernel for (i), (ii), (iii) and (vii) at P1 and P3 (the existing kernel supports P, q and κ);
- MMSE and MMSE-SIC chains at 31.02 dB (regime map).

Labels: "non-exclusive host"; new PyTorch implementations ((iv), (v), (ix), (x), (x′)) are "unoptimized new code, not a cost claim". NVML energy is recorded but reported only as above-idle, with this label.

**4.6 Pre-committed reading** (from the chair plan):
- If (x) or (x′) matches (i) at equal half-steps (BER-ratio CI covers 1 and McNemar p > 0.05 at ≥ 2 of the 3 points), copy alternation is positioned as the binary-spin realization of a bounded-step synchronous lattice update. No algorithmic superiority over p-dits is claimed.
- If (x) is worse with McNemar p < 0.01 at ≥ 2 points, the paper may say only that our symbol-level synchronous variant underperforms at equal half-steps.

## 5. Statistics (`stats_ap.py`)
- **SNR at BER.**
  - Log-linear interpolation at the **last downward crossing**: the pair with BER(s0) ≥ target > BER(s1) after which no point is ≥ target.
  - A zero-error point is replaced by its rule-of-three bound 3/n. The result is then an upper bound, printed "≤". If 3/n ≥ target, the entry is "≤ s1".
  - A curve that never falls below the target is printed "> max".
  - The first-crossing value is also stored, for the record.
- **Cluster bootstrap.** Channel uses are resampled with replacement, independently per SNR point; 2,000 replicates; 95 % percentile intervals for BER and for SNR-at-BER. Clopper–Pearson is shown beside it, for reference only.
- **Paired differences.** The common prefix of uses is resampled jointly and the tails independently.
- **McNemar.** Exact two-sided binomial test on per-use vector errors over the common prefix.

## 6. Item 4: mechanism data
- **(a) Traces.** Seed 103, P1 instances whose MMSE guess is wrong. On the K = 1 and K = 2 sub-problems around the MMSE guess, one anneal with alternation and one without, from the same start and with the same T and q. Per half-step: d_m(t) for every m, the energy, the number of flips, the number of dimensions moving by ≥ 2 levels in one half-step (overshoot), period-2 returns (d_m(t+2) = d_m(t) ≠ d_m(t+1)), and the distance to the truth. Plus population statistics over 200 instances.
- **(b) Grid.** BER against pinning q ∈ {0, 0.1, 0.2, 0.4, 0.8, 1.6} × T ∈ {0.1, 0.2, 0.3, 0.5, 0.8}, alternation on ("a") and off ("s"), plus dimension-scaled pinning c ∈ {0.25, …, 4} without alternation. P1, Ns 32, seed 104, 4,000 uses per cell (fixed n).

## 7. PIMI regime map (existing data plus three new BER points)
The sources are the verified milestone-D/E records (`data/verified_mimo_20261017`). Contents:
- The conversion 31.02 dB = 25 dB Eb/N0 + 10 log₁₀ 4.
- At 20 and 22 dB, PIMI misses 10⁻³ with every published setting.
- At 32×32 QPSK 14 dB, the kernel ratio is 0.74× time and 0.71× energy, with the BER ratio.
- At 31.02 dB, one stage runs at 0.93× PIMI's time.
- New in this protocol: MMSE, MMSE-SIC and K-best BER at 31.02 dB (seed 101, §3.4 rule), and the MMSE / MMSE-SIC chain times (§4.5).

## 8. Item 8: fidelity to the published curves; reported numbers
- **Digitization.** MDI-MIMO arXiv:2304.12830v2 (local `refs_src/mdi.pdf`, p. 9 raster images), Figs. 5 (16×16) and 6 (32×32), panels 4-QAM (DI-MIMO per Table I) and 16-QAM. Curves: MDI-MIMO, MMSE-SIC and MMSE, plus the "theoretically optimal" curve for 16×16 4-QAM.
  - Axes are calibrated on the major grid lines; markers are found by colour mask, a 3×3 opening and centroids (`analysis/digitize_mdi.py`).
  - Reading uncertainty: ±1 px, i.e. ±0.1 dB and ±0.02 decades.
- **SNR matching.**
  - The figure axes read "Eb/N0" while §V-B says "SNR (received power to noise power)".
  - We overlay with Eb/N0 = SNR − 10 log₁₀ b, b = log₂ M (−6.02 dB for 16-QAM, −3.01 dB for QPSK). This is the same group's convention in PIMI (App. 15), and it is consistent with the matched-filter bound (subagent check).
- **Overlay data.** Our MDI-AHC, MMSE-SIC and MMSE (seed 101) and the old curves, on the Eb/N0 axis, with CIs. A per-point difference table at the published SNRs, plus ΔSNR at 10⁻³.
- **DI-MIMO paper.** Its own Globecom 2022 figures (arXiv:2205.05020) are not digitized: no local copy exists and no file is downloaded without the user's permission. The 4-QAM panels of MDI Figs. 5 and 6 are DI-MIMO by MDI's Table I.
- **Resolved ambiguities and their measured cost.** Seed 105, x16 20 dB (MDI-AHC kernel) and q32 13 dB, ≥ 16,000 uses:
  - 2ω for 16-QAM: the text says 4, the definition gives 6; `amb_om2` tests 4.
  - x0/e0 "N(0, 0.001)" as a variance (ours) or as an sd (`amb_x0sd`).
  - Rounding of the per-sub-problem anneals: ceil (ours) or floor (`amb_floor`).
  - SIC ordering: real-stream (ours) or per-user (`sicc`), at 20 and 24 dB.
  - Not tested by run, but tabulated: the non-convergence rule "Ts = 0", which is a no-op because the guess is always a candidate; λ_mean, which is as published for every configuration here; the overloaded Ns, whose effect is the Ns = 8 row; best-by-energy against best-by-distance per anneal; and biased against unbiased MMSE.
- **REPORTED_COMPARISON.md.** Verified primary-source numbers (subagent research: exact location; VERIFIED / abstract-only / UNVERIFIED), with no reimplementation.

## 9. Predictions (frozen; a result outside a range is reported as such)
**Table II, seed 101** (dB; 10⁻³ / 10⁻⁴):

| Row | x16 | x32 | q16 | q32 |
|---|---|---|---|---|
| MMSE-SIC | 24.0–25.0 / 25.8–27.0 | 24.4–25.4 / 26.0–27.5 | 13–16 / 15–19 | 13–16 / 15–19 |
| K-best 32 | 18.6–19.4 / 19.8–20.8 | 20.4–21.4 / 21.8–23.0 | 10.6–11.4 / 12.2–13.0 | 11.1–11.9 / 12.2–13.0 |
| ML (SD) | 17.8–18.8 / 19.0–20.3, ≥ 0.1 dB below K-best | — | within 0.2 dB of K-best | — |
| One stage | 22.5–23.6 / > 27 (P = 0.7) | 22.2–23.2 / > 26 (0.6) | 11.4–12.2 / 13.8–14.8 | 11.6–12.4 / 14.0–14.8 |
| MDI-AHC, published Ns | 19.1–20.0 / 21.0–23.5 | 19.6–20.6 / 21.2–22.5 | 11.4–12.2 / 13.3–14.3 | 12.8–13.6 / 14.5–15.5 |
| Antiphase, published Ns | 18.4–19.2 / 20.3–22.3 | 18.0–18.8 / 19.2–20.2 | 10.6–11.4 / 12.2–13.0 | 10.1–10.9 / 11.7–12.5 |
| MDI-AHC, Ns 8 | 21.2–22.2 / 24.0–26.0 | 22.5–23.5 / 24.0–25.5 | — | — |
| Antiphase, Ns 8 | 20.4–21.4 / 22.5–25.0 | 20.3–21.2 / 21.5–23.0 | — | — |

**Paired claims.**
- Antiphase ahead of MDI-AHC at 10⁻³ (published Ns) by 0.4–1.2 (x16), 1.2–2.2 (x32), 0.4–1.2 (q16) and 2.2–3.2 dB (q32), with the CI excluding 0 at all four.
- x16 against K-best at 10⁻³: "matches" (P = 0.6); at 10⁻⁴, K-best ahead by 0.3–1.5 dB.
- x32: Antiphase ahead of K-best by 2.0–3.0 dB (10⁻³) and 2.0–3.5 dB (10⁻⁴).

**Floor (x16, ≥ 22 dB).**
- For Antiphase (Ns 64) errors, SD-certified ML errors are ≤ 30 % and search failures ≥ 70 %. Of the search failures, ≥ 60 % are solver failures (truth inside a searched box).
- For MDI-AHC, search failures are ≥ 70 %.
- K-best's errors at ≥ 22 dB: ML errors ≥ 50 %.
- The vector error rates of Antiphase and MDI-AHC at 24 dB are within ×0.3–3 of each other.
- SD unfinished at 2×10⁶ nodes: 0.5–3 % at 18 dB; ≤ 0.1 % after 5×10⁷.

**Ablation, seed 102** (BER ratio to (i); P1 / P2 / P3):

| Variant | P1 | P2 | P3 |
|---|---|---|---|
| (ii), (ii′) | ≥ 10 | ≥ 10 | ≥ 100 |
| (iii) | 0.5–3 | 0.5–5 | ≥ 10 |
| (iv) | ≥ 3 (P = 0.75) | ≥ 3 | ≥ 3 |
| (v) | 1–10 | 1–10 | 1–100 |
| (vi) | 1.2–10 | 1.2–10 | 1.2–10 |
| (vii) | 0.5–5 | 0.5–5 | 0.5–10 |
| (viii) | 1–30 | 1–30 | 1–30 |
| (ix) | 0.5–3 | 0.5–3 | 0.5–3 |
| (x) | 0.7–10 | 0.7–10 | 0.7–10 |

Further:
- (x′) is no better than (x).
- PyTorch in-chain solver time relative to (i): (ii) 1–3× at P1; (iii), (vi), (vii) 0.8–1.3×; (v) 1–3×; (viii) 0.5–2×; (ix) ≥ 20×; (x) 0.7–2×.

**Mechanism.**
- Over the (q, T) grid, the alternation-off minimum BER is ≥ 5× the alternation-on minimum (P = 0.8).
- The best alternation-on cell is within ×2 of the frozen (q 0.4, T 0.3).
- Without alternation, ≥ 20 % of the first 50 half-steps show a ≥ 2-level overshoot in some dimension, and period-2 returns occur. With alternation, overshoot is 0 by construction.

**Fidelity** (our curve minus the digitized one, at 10⁻³, after the SNR conversion; old data give +0.2, +0.2, +0.2 and +0.9 dB for MDI-AHC x16, x32, q16, q32):
- MDI-AHC within ±0.5 dB at x16, x32 and q16.
- q32 DI-AHC weaker by 0.5–1.5 dB.
- Our MMSE-SIC better than the published one by 0.1–0.8 dB.

**Ambiguity costs.**
- `amb_x0sd` raises MDI-AHC BER by ≥ 2× at both points.
- `amb_om2` changes BER by ×0.7–2.
- `amb_floor` raises BER by ×1–2.
- `sicc` vs `sic`: ×0.7–1.4.

## 10. Compute plan and ETA
**Workers.**
- hostB: 3 GPUs × 2 workers (equiv → tune → Table II headline → ablation → ML → Ns 8 → one stage → mechanism → amb).
- hostA: GPU7 with 2 workers (x16 AHC kernel), plus 1 CPU worker (K-best / SD, 32 numba threads).
- Tuned variants start once `results/tuned.json` exists. The traces (§6a) run as a separate short job.
- The timing pass (§4.5) runs once GPU7's error counting has finished.

**ETAs** (estimates from the smoke test):
- E2 and tuning by Sun 25 Oct.
- Table II headline rows by Tue 27 Oct; all Table II by Thu 29 Oct.
- Ablation by Fri 30 Oct.
- Timing pass Sat 31 Oct – Mon 2 Nov.
- Everything by Thu 5 Nov.
