# PROTOCOL A5.6: residual-test early stop, budget split, and the review's remaining experiments

**Exploratory.** Written and frozen on 5 Nov 2026, about 03:00 CET, before any A5.6 result on a seed it reports. The SHA-256 is in `STATUS.md` and in `results/a56/SHA256SUMS_A56.txt`, with a read-only copy on hostB. Started under the author's overnight instruction of 4–5 Nov ("<instruction>"), after the author asked for this protocol ("<instruction>"). Nothing here changes `main.tex`. Whether the paper uses any of it is the author's decision.

Seen before freezing, all on dev seed 1020 or as bit-for-bit replays: about 300 uses at P1–P3 for code checks, single batches of split arms for memory, and a local rough simulation with my own MMSE-SIC (no Antiphase). No saved held-out number was re-analysed.

## 1. Why
| Source | Question | Where answered |
|---|---|---|
| `REVIEW_FINAL.md` X1, SA re-tune | SA at modeled equal cycles | A5.5 (running) |
| Length of the frozen schedule | BER against length | A5.4 (running) |
| X2 | Antiphase re-tuned at L = 32P–1024P; SA (S, Ns) split at P1 | §4 G, §4 HS |
| X3 | Production model against float, paired, 1.10 limit | §4 X3 |
| X4 | One random copy per lane: BER at P1–P3 | §4 L. The Genus delta is not done here (ASIC flow, not hostB) |
| X5(a) | q = 0 with T re-tuned | §4 F |
| X5(b) | Returns and returns per move for in-phase and dilution | §8 |
| Performance | Early stop on the residual test; anneals against length; Rmax; κ | §4 A, B, C, D, N |

**Early stop.** For the true x, `‖y−Hx‖²/N0 ~ Gamma(Nr, 1)`: mean Nr, standard deviation √Nr. A use whose current best passes `t ≤ Nr + c√Nr` already looks like noise, so more search cannot be expected to help it. The wrapper computes this residual anyway, so the test costs one comparison and needs N0. The wrapper's zero-radius skip almost never fires: P1 spends 229–257 of 256 anneals per detection, so a guess that is already right still gets anneals.

## 2. Points
| Point | Shape | SNR | Ns | Batch | Saved series |
|---|---|---|---|---|---|
| P1 | x16 | 20 dB | 32 | 2,000 | `abl/x16/mdiane32`, seed 102, 10 batches |
| P2 | x32 | 22 dB | 8 | 1,000 | `abl/x32/mdiane8`, seed 102, 43 batches |
| P3 | q32 | 14 dB | 8 | 4,000 | `abl/q32/mdiane8`, seed 102, 40 batches |
| P4 | x16 | 31.02 dB | 8 | 2,000 | none |

Tuning seed **1020** (unused before A5.6, disjoint from A5.5's 1000 and 1010). Held-out seed **102**. Published-count checks on seed **101**.

## 3. Instrument
`src/trace_a56.py` runs `src/a56lib.py:mdi_trace`, a statement-for-statement copy of `apx.mdi_diag`, with the runner's draws and solver seeds. Per use and checkpoint (start, then after each stage): t = ‖y−Hx‖²/N0 of the better guess and its bit errors. Also anneals per stage and K, radii, and the K of each winning candidate. Per K: flips, half-steps, anneals. `apx.py`, `runner.py`, `mimo.py` are not edited. Method name `a56_<Sk>_<T0>_<T1>_<q>_<κ>_<alt|lane>_<Ns>`, L_K = Sk·2K; other methods run through `apx55.solver_for` or `apx.mdi_solver_for`.

**Replay rule.** A job with `saved` must reproduce that directory's bit errors and erroneous x̂ batch by batch, or it fails.

**Stopping rule** unless a job says otherwise: 100 erroneous uses, 100 bit errors and min uses, or 10⁷ bits. Set `A` runs at least 40,000 uses at P1 and P2. P3 has a 10⁹-bit cap because it runs about 8,000 uses/s. Tuning arms cap at 64,000 uses (P1), 32,000 (P2).

## 4. Runs, in priority order
| Set | Seed | What |
|---|---|---|
| R, R3 | 102 | Replay of (i) at P1–P3 (saved batches); R3 continues P3 to the stop rule; P4 new |
| A | 1020 | (i) at P1–P4, tuning baseline and threshold pick |
| L | 102 | Lane-random copy, schedule of (i), P1–P3 (X4) |
| F | 1020 | q = 0, T = T0 = T1 in {.1,.2,.3,.5,.8,1.2,2.4}, P1–P3 (X5a) |
| D | 1020 | κ in {.15,.3,.6}, P1, P2 |
| C1, C2 | 1020 | Rmax in {1, 2}, P1, P2 |
| S | 102 | Replays with traces: `abl_sa_32`, `mdiahc32` (P1), `mdiahc8` (P2) |
| PC | 101 | Replays: `mdiane64` x16 (14 batches), `mdiane128` x32 (first 20) |
| B | 1020 | (Sk, Ns) split. P1 budget 1: (16,256),(32,128),(64,64),(256,16),(512,8); ½: (128,16),(64,32),(32,64),(16,128); 2: (128,64),(64,128),(32,256),(256,32),(512,16). P2 budget 1: (16,64),(32,32),(64,16),(256,4),(512,2); ½: (128,4),(64,8),(32,16),(16,32); 2: (128,16),(64,32),(32,64),(256,8),(512,4) |
| N | 1020 | Reinvestment: (128, Ns) at P1 Ns 128, 256; P2 Ns 32, 64, 128 |
| HF, HD, HC, HB, HN | 102 | Picks of §5 |
| HS | 102 | SA split: `abl_fam_S_T0_T1_st_Ns`, (S, Ns) = (2,64),(4,32),(8,16),(16,8) at P1, using the cell A5.5 picked for that S. Queued once A5.5's tuning names it |
| G | 1020 | Lengths Sk in {32,64,256,512,1024} × {q .2,.4 × T .1,.2,.3,.5; (T0,T1) (.6,.2),(1.2,.2) × q .2,.4}, P1, P2, capped at 8,000 / 4,000 uses, stop at 30 erroneous uses |
| HG | 102 | Best G cell per length and point, paired with A5.4's frozen schedule at that length; cap 40,000 / 20,000 uses at Sk ≥ 512 |
| X3F | 102 | Float (i) continued past the saved batches, P1 and P2, same stream |
| X3P | 102 | Production model on the same draws, P1 and P2, CPU |
| X3T | new | Production model, row "D128 X64" draws to 100 erroneous uses or 20,000 uses, for a stable Table IV BER; no float pair |

**X3 details.** `src/x3_prod.py` runs the production engine model of `antiphase_asic/PROTOCOL.md` (`ape_model.cpp`, `ape_py.py`, `antiphase_ref.py`, hashes equal to `wl/final/code.sha256`, no kit data, copied to hostB; `mimo.py`, `anefx.py`, `mdi_solvers.py` hash-equal already) in `workload.py`'s `fx_xs` mode: production xorshift, A = 4, SEEDL = max(1, D/32). Passes before starting: `workload.py` on hostB reproduces P2 seed 42 (213 bit errors of 256,000); my driver equals `workload.py` given the same draw. Stop at 2,000 erroneous uses per arm or 400,000 uses (P1), 300,000 uses (P2). Priority below N, one process at a time at nice 10, on 4 CPU threads, 8 once A5.4 has ended (hostB's 24-core cap stands; `workload.py` used 16).

## 5. Selection (tuning seed only)
- **F:** lowest BER at each point goes to HF in every case; the review wants the answer either way.
- **D, C:** lowest BER goes to the held-out seed only if its paired ratio to (i) is ≤ 0.9.
- **B:** lowest BER per budget goes to the held-out seed only if Sk ≠ 128 and its ratio to (128, same budget) is ≤ 0.9, together with that comparator.
- **c:** the largest c in {.5,1,1.5,2,3,4,6} whose paired BER ratio to no stop has upper 95% bound ≤ 1.10 on set A. If none passes, the point gets no stop.
- **N:** among (128, 2Ns) and N's arms with stop at that c, those with mean cycles ≤ (i)'s no-stop mean; lowest BER goes to HN.
- **G:** lowest BER per (length, point) goes to HG.

## 6. Cost and x
Cycles per anneal at K: L_K + F_K, Eq. (4)'s Antiphase cost, with F_K measured on that run. Mean cycles per use: Σ anneals × (L_K + F_K) up to the stop. Host work is not counted. **Modeled cycles only, no time and no energy. Averages only: worst-case latency is unchanged, and the p99 and maximum are reported.** `ceil(Ns/t)` inflates small Ns, so B reports measured cycles and flags arms beyond ±15% of the budget.

## 7. Same test for the others
An early stop is not Antiphase's property. SA and AHC get the same test at the same c: full traces (set S) and, for saved runs without traces, start-only (uses passing at the start take MMSE-SIC's bit errors, others keep the saved result; no anneals needed). K-best has no comparable loop; none is claimed.

## 8. Mechanism (X5b, `src/mech_a56.py`)
Same 200 sub-problems, start and generator as `src/mech_trace.py` (seed 103, x16 20 dB, K = 1, 2, S = 128P). Arms: alternation, in-phase (`colour_classes` mode 'dim', activity 1/P), dilution (activity 1/P), lane; T .3, q .4; plus in-phase at its tuned q .8, T .5, and alternation at q 0. Reported per K: period-2 returns, flips per half-step, returns per move, 95% bootstrap over sub-problems. Alternation must reproduce `results/mech/traces_seed103.json`.

## 9. Analysis (`src/analyze_a56.py`)
Paired cluster bootstrap over uses (4,000 replicates, common prefix of uses, same draws), exact McNemar. Stop tables per c: stop share at the start, mean stage, BER ratio with CI, cycles saved, N0 misestimated by ±1 dB at the picked c. BER and cycles against stage count S′ (free from checkpoints). Share of anneals, cycles and wins per K. X3: production/float ratio with CI, 1.10 limit, plus the second-draw comparison.

## 10. Reported and wording rules
- "Cuts mean modeled solver cycles by X at BER within 10%" only if the held-out upper bound is ≤ 1.10, and only with "averages; worst-case latency unchanged; N0 assumed known" or the ±1 dB result.
- No SA or AHC ranking with a stop unless the same test is applied to them (§7). Without that, early stop only says something about Antiphase against itself.
- Split, Rmax, κ and length results compare Antiphase with itself unless SA gets the same treatment.
- q = 0 (review disagreement 3): CI above 1 means pinning needed at that point; CI including 1 means retract "needed" and write "no detected difference", never "unnecessary"; CI below 1 means q = 0 is better there and it goes to the author.
- Lane: BER tie means the hardware claim is limited to simplicity. Without a Genus delta there is no cost claim.
- X3: passes only with upper bound ≤ 1.10 at that point. Otherwise report the factor and keep the fallback sentence.
- Adopting a new operating point means rerunning Tables II–IV, Figs. 3–4 and ASIC replays: the author's decision, and my threshold for proposing it is a ≥ 2× held-out BER gain at equal modeled cycles.

## 11. Checks before freezing
`src/test_a56.py`, `src/test_a56b.py`: `ape` equals `mimo.anechoic` bit for bit (κ 0 and .3); `mdi_trace` equals `mdi_diag` (output, generator state, anneal count); last checkpoint equals output; residual never rises; checkpoint 0 is the start; replays of saved batches pass for (i) at P1–P3, SA, AHC and seed 101; lane mask has one active copy per coordinate; stop evaluator on a hand case; flips per anneal within 5% of A5.4's calibration; apx55 methods equal through the trace path; largest arms fit (peak under 1.5 GB); planner and analysis run on a scratch root. All passed before this freeze except X3's, which must pass before X3 starts (failure means X3 is logged and left).

## 12. Compute
hostB **GPU0 and GPU1** by UUID, with A5.4 (never GPU2–3, which carry A5.5 and its deadline). 2 workers per GPU while A5.4 runs, 4 after. 2 CPU threads per worker, 20% GPU memory cap, no launch below 8 GB free, stop our newest below 2 GB. CPU: the 24-core cap of `PROTOCOL.md` stands, no new worker while the load average is above 20. Results only under `<SCRATCH>/ap_ber_20261024/results/a56`, logs under `logs/a56`. Untimed: no time from a 5090 is reported. Other processes on the account or host are never touched. A job failing 3 times is left, logged and diagnosed.

Estimated cost: about 100 worker-hours on GPU, 15–30 h of wall clock; X3 about 10 CPU-thread-days at most. If A5.5's deadline (Tue 10 Nov 18:00 CET) is at risk, A5.6 is not the cause, as it does not share GPUs with A5.5.

## 13. Predictions (not revised)
| Claim | P |
|---|---|
| P1: picked c in [1, 2], cycles saved 2–4× | .6 |
| P2: picked c ≥ 1.5, cycles saved ≥ 3× | .6 |
| P3: cycles saved < 2×, as P3 starts from MMSE alone | .7 |
| P4: cycles saved ≥ 10× | .7 |
| Reinvestment gains ≥ 1.5× held-out BER at equal mean cycles at P1 or P2 | .5 |
| Reinvestment reaches SA's BER at P1 at Ns 32's cycles | .2 |
| A split with Sk < 128 beats (128, Ns) by > 10% on the tuning seed at budget 1, P1 or P2 | .6 |
| Lane ratio to (i) in [.8, 1.25] at P1–P3 | .7 |
| q = 0 re-tuned: CI above 1 at P3 | .7; at P1 .5 |
| In-phase returns ≥ 3× alternation's at K = 1 | .7 |
| Length re-tune gains ≥ 1.2× at Sk ≥ 512 on the held-out seed | .5 |
| X3: production/float point estimate in [.9, 1.2] at P1 and P2 | .7; upper bound ≤ 1.10 at both .3 |
