# PROTOCOL A5.18, part 1: Arpeggio (first-accept) layouts at Chord's clocks, D = 32/64/128

Written and frozen on 11 Nov 2026, before any A5.18 tool ran. The go was the user's "Start both" (11 Nov 2026, about 05:00 CET), approving `../PLAN_A517_A518_20261111.md`.
- **Part 1** (this file) covers the layouts and their sign-off.
- **Part 2** covers Table IV workloads: fixed-point BER, command replay and power. It will be frozen as `PROTOCOL_A518_part2.md` before any Arpeggio replay or power run.
- The paper does not change without the user.

## 1. Question
The blind reviewers (round e, 11 Nov) found that half of routed Arpeggio's "26% less time" at 16 users comes from its clock: Arpeggio met 1.00 ns at D = 32, Chord met 1.15 ns. At D = 64 the clocks are the other way round. They ask for Arpeggio in Table IV "at the same target period as Chord", for all three D.

This part builds the layouts that make that possible.

## 2. Designs (frozen inputs, as A5.11 §2)
- **Arpeggio:** `ape/rtl/ape_engine_fa.sv`, SHA-256 `ada3059e94fd…`, production build.
- **Chord:** v1.4 `ape_engine.sv`, `67367973dd0b…`.
- **Synthesis:** `flow/run_syn.sh` / `syn_generic.tcl` at 1000 ps, 6 CPUs, effort medium, with the same memory wrapper and macro lists.
- **Instances:** `ape_engine_D{32,64,128}_A4_SEEDL{1,2,4}`.
- **P&R:** `flow_v2_20261024/run_v2.sh` + `pnr_v2.tcl`. The md5 values on hostB and hostC are equal: pnr_v2 2bd52949…, sdc_scale ce77aa59…, closure_pass 04c5a777…. Utilisation 0.60, 8 CPUs, stop `final`.
- **Existing layouts:**

| Engine | D | Layout | Period (ns) | Status |
|---|---|---|---|---|
| Chord | 32 | `ape_d32_p1150_r4` | 1.15 | accepted |
| Chord | 32 | `ape_d32_r4b` (hostC) | 1.00 | missed: −4 ps, 1 DRC |
| Chord | 64 | `ape_d64_r4` | 1.00 | accepted |
| Chord | 128 | `ape_d128_p1200_r4` (hostC) | 1.20 | accepted |
| Arpeggio | 32 | `fa_d32_p1000` | 1.00 | accepted |
| Arpeggio | 32 | `fa_d32_p1150` | 1.15 | accepted (A3) |
| Arpeggio | 64 | `fa_d64_p1000` | 1.00 | missed: −6 ps |
| Arpeggio | 64 | `fa_d64_p1150` | 1.15 | accepted |
| Arpeggio | 128 | none | | |

## 3. New runs (all launched together; none is conditional on another's result)
| Key | Engine, D | What | Host, CPUs |
|---|---|---|---|
| **C1** | Chord 32 | one closure pass (`run_closure.sh`, `closure_pass.tcl`) on `ape_d32_r4b` at 1.00 ns | hostC, 8 free CPUs |
| **C2** | Arpeggio 64 | one closure pass on `fa_d64_p1000` at 1.00 ns | hostB 16–23 |
| **N1** | Chord 64 | fresh P&R at 1.15 ns from `ape/syn/v14_d64_p1000`; SDC by `sdc_scale.py` | hostB 8–15 |
| **S128** | Arpeggio 128 | synthesis at 1000 ps, SEEDL 4 | hostB 0–5 |
| **P128a** | Arpeggio 128 | P&R at 1.20 ns (Chord's period), after S128 | hostB 0–7 |
| **P128b** | Arpeggio 128 | P&R at 1.25 ns, pre-staged | hostC, 8 free CPUs |

C1 and C2 apply **the same single closure pass to each engine's only near miss under 10 ps**, so neither engine gets more effort than the other. No closure pass was used on any accepted layout so far. A layout accepted after the pass is labelled "with one closure pass".

**Acceptance:** as A5.11 §3. Every one of these must hold:
- TT setup WNS ≥ 0 in every group;
- hold WNS ≥ 0;
- DRC 0;
- connectivity 0;
- FLOW_V2_DONE_FINAL.

**Hangs:** a run hung for more than 3 h in one step is killed, kept and relaunched once.

## 4. Same-period pairs (the primary output)
For each D, the **primary pair** is both engines at the **shortest period at which both have an accepted layout**:
- **D = 32:** 1.00 ns if C1 is accepted; otherwise 1.15 ns (A3 pair).
- **D = 64:** 1.00 ns if C2 is accepted; otherwise 1.15 ns (N1 and `fa_d64_p1150`). If N1 also fails, a 1.20 ns pair (`fa_d64_p1200` plus a new Chord run).
- **D = 128:** 1.20 ns if P128a is accepted. Otherwise 1.25 ns if P128b is, with a new Chord run at 1.25 ns added then. Otherwise both engines walk on in 50 ps steps.

**Also reported:**
- every other same-period pair that exists;
- each engine at its own shortest accepted period (today's "each at its best clock" reading).

## 5. Sign-off for every layout used in a pair (part 1, R3)
- DRC, connectivity, hold and placement, from the flow reports.
- **Conformal LEC** RTL → fv_map → synthesis → routed, as gate_r4 / A5.11 G3, for Arpeggio D128 and for any new accepted layout.
- **SS setup:** `scripts/sta_ss_v3.tcl`, with the same corner and method as Table IV's SS column.
- **Area:** die, core, std-cell logic, physical-only and macro (`area_public.txt`), for both engines.

## 6. Predictions (frozen)
| Run | Prediction | Probability |
|---|---|---|
| C1 | accepted | 0.6 |
| C2 | accepted | 0.6 |
| N1 | accepted | 0.95 |
| P128a | accepted | 0.6 |
| P128b | accepted | 0.75 |

Arpeggio's std-cell area at D = 128 is within ±6% of Chord's: probability 0.7.

## 7. Compute and safety (as A5.11 §7)
- **hostB:** at most 24 threads for this work (CPUs 0–23), `nice` 5–10.
  - The A5.17 GPU work runs alongside and uses at most 4 CPU threads.
  - If A5.17 needs CPUs while all 24 are taken, P&R keeps priority, and A5.17 waits or runs at nice 19.
- **hostC:** 16 threads on CPUs that mpstat shows idle at launch, `taskset`.
- HOME and XDG point under `<SCRATCH>/antiphase_asic_20261017/home`.
- All output goes under `<SCRATCH>/antiphase_asic_20261017/a518/`, with log `a518/RUNLOG.txt`.
- Kit-derived files move only server to server.
- Never touch other users' or the user's other jobs.
- **Stop rule:** if no D = 128 Arpeggio layout is accepted by 15 Nov 12:00 CET, stop. Table IV then gets D = 32/64 rows only.
