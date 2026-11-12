# Amendment A5.12 (exploratory): parallel-trial cost sensitivity at 5, 3 and 2 cycles per iteration

**Approval.** On 7 Nov 2026 about 15:20 CET the author said "<instruction>" ("proceed as you judge right") after my proposal to run this check. Written and frozen before any A5.12 run. It does not replace A5d/A5.2; it is reported beside them.

## 1. Why
- The paper charges a parallel-trial single-flip engine C_PT = I(1 + ⌈log₂N⌉), which is 7–10 cycles per iteration at N = 64–384.
- Matsubara et al. (CISIS 2017) report "five clock cycles per trial phase" for the Digital Annealer's FPGA engine at N = 1024.
- From existing runs (`<PROJECT>/work/da_cost_sensitivity_20261107/README.md`), a 5–6-cycle DA keeps Antiphase ahead at P2/P3 by bracketing. P1 is open, and 2–3 cycles is untested at every point.

## 2. What runs
**Budget.** For a sub-problem (shape, K):
- L = 128·2K and F = φ_K·L, with φ from `tuned_a52.json` `flip_phi` (the A5d calibration);
- I_c = max(1, round((L + F)/c)) iterations, for c ∈ {5, 3, 2}.

Everything else is A5d's parallel trial (`apx.snowball_par`): Glauber roulette-wheel single flip, geometric T0 → T1, random start, best visited state, inside MDI.

| Sub-problem | c = 5 | c = 3 | c = 2 |
|---|---|---|---|
| x16 K1/K2/K3 | 57/134/214 | 96/223/356 | 144/334/534 |
| x32 K1/K2/K3 | 63/165/258 | 104/274/430 | 157/412/645 |
| q32 K1 | 66 | 110 | 164 |

**Tuning.** P1 only (x16, 20 dB, Ns 32), seed 1000, as in A5/A5.2:
- **Cells:** the 18-cell union of A5 and A5.2, i.e. T0 ∈ {0.3, 0.6, 1.2, 2.4} × T1 ∈ {0.05, 0.15, T0} plus T0 ∈ {0.075, 0.15} × T1 ∈ {0.0125, 0.025, 0.05}. There are 54 cells in all.
- **Per cell:** 4,000 uses, batch 2,000, bit cap 4,000·64.
- **Pick per c:** fewest bit errors, then fewest erroneous uses, then grid order (A5 cells first).
- **Corners:** a pick on the grid's low corner (T0 0.075 or T1 0.0125) is reported; the grid is not extended.

**Held-out.** Seed 102, on the same draws as (i), with batch sizes equal to (i)'s: P1 2,000, P2 1,000, P3 4,000.
- **Pick reuse:** the P1 pick of each c is reused at P2 (x32, 22 dB, Ns 8) and P3 (q32, 14 dB, Ns 8). This is the A5d kill-arm privilege and the arm behind the paper's ratios 1.40, 14 and 2,500.
- **Stopping rule:** the A5.2 rule unchanged (runner defaults with min_uses 8,000 / 4,000 / 8,000).

**Not run:** per-point tuning at P2/P3, c = 1 (not reachable for one chain, because evaluate, select and update are dependent), and other points.

## 3. Comparison and terms
- **Reference:** (i) Antiphase frozen held-out, `results/abl/{x16/mdiane32, x32/mdiane8, q32/mdiane8}` on hostB (read-only).
- **Statistic:** the ratio PT/(i) of bit errors on the batch-aligned common uses, with a paired cluster bootstrap 95 % CI (`a56an.boot_ratio`, B = 4,000) and an exact McNemar test.
- **Same-draws check:** d_true is checked on common erroneous uses, as in `analyze_a55.py`.
- **Terms per (point, c):**
  - **PT worse:** CI lower bound > 1;
  - **PT better:** CI upper bound < 1;
  - otherwise **no detected difference**.

## 4. What the paper may say (only by the author's decision)
**c = 5 is the cost a DA paper reports.** c = 3 and 2 are sensitivity only, with no hardware source, so no text may claim "at any cost".

| c = 5 outcome | Statement |
|---|---|
| PT worse at P1, P2 and P3 | "Even at a Digital Annealer's reported five cycles per iteration, parallel trial stays worse at every point." |
| P1 no detected difference; P2/P3 worse | "...worse at every point at our modeled cycles; at five cycles per iteration P1 shows no detected difference, P2/P3 stay worse." The Table I and Fig. 3 claims "leads parallel trial at equal modeled cycles" must carry that scope. |
| PT better at any point | Stated plainly where it holds. Every "leads parallel trial" claim is scoped to our cost model, with the c = 5 result beside it. |

The crossover c (where PT stops being worse) at each point is reported from c = 3 and 2 in every case.

## 5. Predictions (mine, before any run)

| Point | c = 5 | c = 3 | c = 2 |
|---|---|---|---|
| P1 | ratio 0.95–1.2; worse .15 / no difference .70 / better .15 | 0.7–1.0; .10 / .55 / .35 | 0.6–0.95; .05 / .45 / .50 |
| P2 | 2–5; worse .95 | 1.2–2.0; worse .75 | 0.9–1.6; worse .45, no difference .50 |
| P3 | 300–1,000; worse .99 | 30–300; worse .97 | 5–100; worse .90 |

## 6. Compute and rules
**Where.** hostA GPU7 (B200, UUID <GPU_UUID>), 2 workers, threads 2. Untimed: no timing is reported.
- **GPU guard:** launch only with no foreign compute process on GPU7. If one appears, our workers stop and resume when it is gone (idle-with-yield).
- **CPU guard:** our hostA processes stay ≤ 12 cores.
- **Files:** under `<SCRATCH>/ap_ber_20261024/a512/` on hostA. Code is copied server to server from hostB's `src/` and `code_mimo/src/`, plus one change: the `c<k>` budget in `apx.py`. hostB is only read.
- **A5.8 is not touched.**

**Expected time:** 2–4 h. Wall-clock cap 24 h.

**After held-out:** no re-tuning, no added arms or c values. Code: `make_plan_a512.py`, `select_a512.py`, `analyze_a512.py` and `supervise_a512.sh` in `a512/src/`.
