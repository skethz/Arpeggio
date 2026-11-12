# Amendment A5 (with the A5.1 refinements folded in before freezing): the price of parallelism

Written Sun 25 Oct 2026, 00:05 CEST. Frozen before any A5 run.

**What came before.**
- Base protocol: PROTOCOL.md (SHA-256 `2948d98a…79bb`). Its rules apply unless changed here.
- Requests: framing B (`plan_20261024/antiphase_framing/FRAMING_B_on_A.md` §6), refined by the chair check (`reviews_20261024/antiphase_framingB_chair_check.md` §C).
- Development checks only, before freezing: `src/test_a5.py` and `src/test_a5b.py` on dev seeds 9600/9700, ALL PASS. They confirm three things:
  - the colour classes partition the spins;
  - at c = N/2 every class holds two spins with J = 0 between them (exact chromatic sweep);
  - every new method returns constellation levels.

**Compute.** hostB GPU0 only (RTX 5090, <GPU_UUID>), untimed. GPU1/GPU2 run another of the author's projects and are not used; GPU3 belongs to another project. Before every launch the supervisor checks that GPU0 has no compute process outside `ap_ber_20261024`; if it finds one, it waits and launches nothing. No timing is reported from this amendment.

**Seeds.**
- Tuning on seed 1000 only.
- Held-out: seed 102 at the ablation points P1 (x16, 20 dB, Ns 32), P2 (x32, 22 dB, Ns 8), P3 (q32, 14 dB, Ns 8); seed 101 on the Table II uses; seed 104 for the mechanism grid.
- Every variant gets a 12-cell tuning grid at the stated points. Selection rule as before: fewest bit errors, then fewest erroneous uses, then plan order.
- Held-out stopping rule as in PROTOCOL §3.4: ≥ 100 erroneous uses and ≥ 100 bit errors, capped at 10⁷ bits, with minimum uses 8,000 / 4,000 / 8,000 at P1 / P2 / P3.

## 1. Cycle model (C11; labelled model, used for the budgets below)
Per anneal of a sub-problem with N spins, P = 2K copies and L = 128·P half-steps:

| Solver | Modelled cycles per anneal | Notes |
|---|---|---|
| Antiphase | L + F | F = flips per anneal; Alg. 1 serialises one row update per flip. F = φ·L, with φ measured per point and K on seed 1000 (`src/calib_flips.py`; mechanism traces gave φ ≈ 0.36) |
| Parallel-trial single flip, I iterations | I·(1 + ⌈log₂ N⌉) | one parallel evaluation plus a log-depth selection; one flip per iteration |
| Sequential SA, S sweeps | S·N + F_SA | |
| Colour sweep with c classes | 128·c + F | |

## 2. A5d: parallel-trial single flip (the gate)
**Algorithm.** Every iteration:
1. Evaluate the Glauber probabilities p_i = 1/(1 + exp(ΔE_i/T)), ΔE_i = 2 s_i u_i, for all spins in parallel.
2. Select one spin with probability p_i/Σp.
3. Flip it (rejection-free) and update the fields incrementally.
4. If Σp is not positive and finite, fall back to one random-scan Glauber step instead.

Cooling is geometric T0 → T1, the start is random, and the best visited state is returned, as for every variant inside MDI. Code: `apx.snowball_par`. The paper calls it "parallel-trial single flip"; Snowball's roulette-wheel form is one instance.

**Budgets.**
- (a) **Equal modelled cycles:** I_c = round((L + F)/(1 + ⌈log₂ N⌉)). That is about 0.17–0.19·L.
- (b) **Equal flips:** I_f = round(F).

**Tuning.** 12 cells (T0 ∈ {0.3, 0.6, 1.2, 2.4} × T1 ∈ {0.05, 0.15, T0}) per budget, at each of P1, P2, P3 on seed 1000.
- **Primary arm:** the P1 pick reused at P2/P3. This is the same privilege Antiphase had: one schedule tuned at 16 users.
- **Sensitivity arm:** the per-point picks, compared with Antiphase's per-point re-tuned results of A3.

**Kill rule (pre-registered; chair §C).** If the parallel trial at ≤ Antiphase's modelled cycles per anneal (budget (a), primary arm) has an upper 95 % BER-ratio CI ≤ 1 against (i) at ≥ 2 of P1–P3, framing B is **withdrawn**. The fallback text of the chair check §C then applies.
- If only the sensitivity arm or budget (b) meets that condition, this is not a kill by the rule, but it is reported with the same prominence.
- **What is said in each case:**
  - **Kill:** "at equal modelled cycles, a parallel-trial single-flip engine reaches lower BER; synchronous copy desynchronisation is then justified only for engines without a global N-way selection (PIMI/SCA class)".
  - **Not killed, and the parallel trial is worse with McNemar p < 0.01 at ≥ 2 points:** "at equal modelled cycles, Antiphase's multi-flip synchronous half-steps make more progress than single-flip selection".
  - **Otherwise:** "comparable at equal modelled cycles"; report both budgets.

## 3. A5a: sequential Metropolis SA, the dB price
**Re-tuning.** The old pick 2.4 → 0.05 was a corner of the grid. The grid is extended on seed 1000 at P1 with T0 ∈ {2.4, 4.8, 9.6} × T1 ∈ {0.0125, 0.025, 0.05}. The pick is taken over the union with the original 12 cells; it is called `sa2` and applies to all of A5a. If it again lies on a corner, that is reported and the grid is not extended further.

**Sweep-count series.** S ∈ {1, 2, 4, …, 128} sweeps with the sa2 schedule compressed over S, at P1 and P2 (seed 102). Together with the colour sweep and the parallel trial, this places BER against modelled cycles per anneal on one curve.

**dB conversion on the seed-101 Table II uses**, SNR at 10⁻³ and 10⁻⁴ with paired CIs against Antiphase:
- **x16 at the published Ns 64**, 0.5 dB grid 16.5–22.5 dB. It fits on one GPU: about 15 det/s per worker.
- **x32 at Ns 8**, against Antiphase's Ns 8 row.
  - The published Ns 128 does not fit: measured SA rate 2.5 det/s at Ns 8, and Ns 128 is more than 10× the work, i.e. more than 300 worker-hours.
  - Tier 1: a 1 dB grid 18.5–24.5 dB, 7 points.
  - Tier 2 (lowest priority): the 6-point 0.5 dB fill.

## 4. A5b: colour-count sweep
**Rule.** Antiphase's rule is unchanged: SCA with pinning, constant T, best of trajectory, equal decisions per spin. With c colour classes there are L = 128·c dependent steps.

**Classes.** Copy p together with user group g, taking both the I and Q dimensions of those users. The series:
- c = 1 (fully synchronous);
- c = P (Antiphase);
- c = 2P, 4P, …;
- c = P·N_t = N/2. The real lift makes a user's I and Q columns orthogonal, so this is an exact chromatic sweep (verified: |J| within a class is about 3×10⁻⁸).

So m = c/P ∈ {1, 2, …, 16} at x16 and {1, …, 32} at x32, plus c = 1.

**Tuning.** (q, T) is re-tuned per c on seed 1000, 12 cells (q ∈ {0.2, 0.4, 0.8} × T ∈ {0.1, 0.2, 0.3, 0.5}), at P1 (4,000 uses) and P2 (2,000 uses). Held-out uses seed 102 at P1 and P2. The frozen (0.4, 0.3) curve is also run at P1, as a sensitivity.

**Controls** (tuned at P1, 12 cells; held-out at P1 and P2):
- **b1:** P colours by dimension, with all copies of those dimensions in phase (activity 1/P).
- **b2:** variant (x) diluted, each dimension eligible with probability 1/P per step.

**Knee (pre-registered).** At least 80 % of the log-BER gain from c = 1 to c = N/2 is reached at c = P, at both P1 and P2.

## 5. C2 controls
- **Alternation off.** The (q, T) grid is extended beyond the old corner on seed 104 at P1: q ∈ {1.6, 3.2, 6.4} × T ∈ {0.8, 1.6, 3.2}.
- **(iv) dimension-scaled pinning,** re-tuned per point on seed 1000 (16 cells: c ∈ {0.5, 1, 2, 4} × T ∈ {0.3, 0.6, 1.2, 2.4}, q0 0.4), with held-out seed 102 at P1–P3.

## 6. A5c (analytic only)
The hardware difference between alternation and dilution:
- Alternation: a static bank of N/P comparators, each serving one copy's spins in turn, and no mask.
- Dilution: N gated comparators, since any spin can be active, plus a mask generator for N Bernoulli(1/P) draws per step: ⌈log₂ P⌉ random bits and a comparator per spin, or an LFSR tap tree.

Both are counted against the Antiphase engine's decision lane (comparator plus RNG bits). On a GPU the extra random draws cost almost nothing (one Philox4x32 call gives 128 bits), so only the SIMT slot structure is noted.

## 7. Optional, CPU only
A K-best K-sweep, K ∈ {8, 16, 64, 128} (K = 32 exists), on the seed-101 Table II uses: x16 16.5–24 dB, x32 18–26 dB. Same stopping rule. No EP is implemented.

## 8. Predictions (frozen)
**A5a.**
- The sa2 pick lies inside the extended grid (P 0.6), with tuning-seed BER ≤ 9.8×10⁻⁵.
- In the sweep series, BER falls monotonically with S. SA first matches (i)'s BER at some S* ∈ [8, 64] at P1 and at P2.
- Table II, SA (x16, Ns 64): 18.3–18.9 dB at 10⁻³ and 19.7–21.0 dB at 10⁻⁴. Against Antiphase: −0.1 to −0.7 dB and −1.0 to −2.3 dB.
- Table II, SA (x32, Ns 8): 20.0–20.8 dB and 22.0–23.3 dB. Against Antiphase Ns 8: −0.1 to −0.9 dB and −0.3 to −1.6 dB.

**A5b.**
- c = 1 is ≥ 10× worse than c = P at P1 and P2.
- BER(N/2)/BER(P) ∈ [0.2, 1.0].
- The knee rule holds at both points (P 0.6).
- b1 is ≥ 10× worse than (i) at P1 and P2 (P 0.8), because copy coherence makes it oscillate.
- b2 is ×0.5–3 of (x) at P1, and better than (x) at P2.

**A5d.** BER ratio to (i):
- equal modelled cycles: P1 0.5–3, P2 0.5–5, P3 0.3–3;
- equal flips: P1 0.3–2, P2 0.3–3, P3 0.3–3;
- probability that the kill rule triggers: 0.35. A dev sample (dev seed 9600, placeholder schedule) gave a parallel trial at equal flips 3.3×10⁻⁴ against Antiphase 7.3–8.9×10⁻⁴ at P1.

**C2.**
- The best alternation-off cell on the extended grid stays ≥ 5× worse than (i) at P1 (P 0.6).
- Re-tuned (iv) stays ≥ 3× worse than (i) at P2 and P3 (P 0.75).

**K-sweep.**
- x16, K = 128: 18.4–18.8 dB at 10⁻³.
- x32, K = 128: 19.0–19.8 dB at 10⁻³.
- x32, K = 8: 21.5–24 dB.

## 9. Cost and ETA (one GPU)
**Basis.** Worker-hours come from the measured 5090 rates per worker:
- Antiphase x16 Ns 32: 74–205 det/s;
- SA: x16 Ns 32 13.4, x16 Ns 64 15.4, x32 Ns 8 2.5 det/s;
- colour sweep: m = 4 54 det/s; m = 16 (dev) about 8 det/s;
- parallel trial: 170–400 det/s at x16.

The uses come from the stopping rule, using the Table II and ablation counts as templates.

| Block | Worker-h |
|---|---|
| Tuning: pt 0.3, sa2 0.7, b1/b2 0.2, (iv) 0.5, colour x16 1.8, colour x32 4.5 | ≈ 8 |
| A5d held-out | ≈ 1 |
| A5a sweep series: P1 2, P2 14 | ≈ 16 |
| A5a Table II x16 Ns 64 | ≈ 18 |
| A5a Table II x32 Ns 8, tier 1 (1 dB) | ≈ 33 |
| A5b held-out per-c tuned: P1 1.5, P2 13.5 | ≈ 15 |
| A5b frozen P1 | ≈ 1.5 |
| Controls b1/b2 | ≈ 2 |
| C2 | ≈ 1.2 |
| **Tier 1 total** | **≈ 96** |
| Tier 2 (x32 0.5 dB fill) | ≈ 28 |
| K-sweep | CPU only, ≈ 3 CPU-h on 8 threads |

**Throughput on one GPU.** GPU0 runs 6 concurrent workers (2 threads each). Together with the CPU worker, that is at most 14 cores, against hostB's 24-core cap. These PyTorch workloads are launch-bound, so 6 workers deliver an estimated 3.5–4 worker-hours per GPU-hour.

| | GPU-hours | Wall time | ETA (launch Sun 25 Oct, about 00:30) |
|---|---|---|---|
| Tier 1 | ≈ 24–28 | 24–28 h | Mon 26 Oct, 01:00–05:00 |
| Tier 2 | +7–8 | — | Mon 26 Oct, about 13:00 |
| Pessimistic case: per-worker rates halve under contention | — | tier 1 ≈ 50 h | Mon 26 Oct, evening |

Everything fits before Wed 28 Oct with margin, and the total stays under the 36 GPU-h budget, so nothing needs to be cut.

**If cuts become necessary, in this order:**
1. Tier 2.
2. The frozen-(q, T) P1 colour curve.
3. The P2 sweep-series points S = 1–8.
4. The A5b P2 points m = 2 and 4.
