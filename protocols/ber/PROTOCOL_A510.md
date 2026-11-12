# PROTOCOL A5.10: fused first-accept SA (re-test in the update path); RTL cycles and re-costed picks (exploratory)

- **Author's go to freeze:** 7 Nov 2026, "Freeze it". It answered "Freeze a protocol today for the CPU-only fused first-accept gate?", which followed the advice comparison in `<PROJECT>/work/advice_20261107/SYNTHESIS.md`.
- **Running needs its own go.** Stage 1 starts on a further go from the author. Stage 2 needs a separate go, and A5.8 must have finished first.
- **Written:** 7 Nov 2026, about 03:00 CET. Every section, including the predictions, was written before any A5.10 code was written or run.
- **Hash:** SHA-256 in `rtl_a510/SHA256SUMS_A510.txt` on hostB.
- **Scope:**
  - Stage 1: RTL cycle counts and a re-costing of saved A5.5 tuning data, on CPU only.
  - Stage 2: BER of re-costed picks on GPU.
  - No timing, area, energy or kit data.
  - A5.8 is untouched. The paper changes only on the author's decision.

## 1. Question
**Fused first-accept (FX)** is first-accept SA with rule (2) on the same D lanes, with one change:
- A lane's per-pass threshold is computed once, in D2, and kept.
- After each row update, the updated fields are compared with the kept thresholds inside the R-port path. The next acceptance is therefore found without going back through D0–D2.

Its semantics are those of A5.5's first-accept (FA): the accepted-lane sequence is the same under the same per-pass random numbers.

The questions:
- **(a) RTL cycles.** How many cycles does FX save against v1.4 FA at the A5.5 B = 1 picks, at one context (latency) and at four (Table IV)? Does it still save cycles against FA given at least as many register bits (FA at six and eight contexts)?
- **(b) Re-costed picks.** Under FX's cost, which rule-(2) cells fit within Antiphase's cycles, and what BER do they reach?

## 2. What the records settle
- **Semantics and random numbers** (A5.5 §2, §8):
  - The Philox build draws one number per (sweep, copy, lane).
  - FA's re-test redraws the same u, while T and q stay fixed within a pass. So the same per-pass thresholds give the same decisions.
  - The rule-(2) first-accept BER of A5.5 (float, `apx55.py`) is a property of these semantics. It therefore carries over to FX once FX passes the accepted-lane check.
- **A5.9 counts** (`RESULT_A59.md`, `results_a59/A59.json`):
  - FA at A = 1 takes 3·tests + 2·F cycles, and Antiphase (AP) 3·L + F + n₁.
  - At A = 4, FA ran at 0.81–1.09 of tests + F, and AP at 0.81–0.99 of L + F.
- **Model ratios on the dev stimulus** (A59.json per-K counts; mean of per-K ratios; P1 S = 64, P2 S = 32, S·P = S·2K). These are model numbers, not predictions of RTL cycles.

| | P1 | P2 |
|---|---|---|
| Throughput, FX (S·P + F) over FA (tests + F) | 0.76 | 0.63 |
| Throughput, FX over AP (L + F) | 0.61 | 0.42 |
| Latency at A = 1, fx2 (3·S·P + 2·F) over FA (3·tests + 2·F) | 0.74 | 0.58 |
| Latency at A = 1, fx3 (3·S·P + 3·F − F_last) over FA | ≈0.83 | ≈0.72 |

- **Held-out flips of the existing B = 1 picks** (`results/a55/flips.json`, sha `572b1fe8…`; (i)'s costs as in A5.5's `ref_cost`):
  - P1 `abl_far_64_0.1_0.1_0_rand_32`: F = 35.3 / 178.5 / 340.8, so x_F′,held = 0.633.
  - P2 `abl_far_32_0.1_0.1_0_rand_8`: F = 54.3 / 220.7 / 365.1, so x_F′,held = 0.411.
  - Under the current FA cost, the same picks have x_F,held 0.862 and 0.649.
- **Not settled:** the fixed-point fidelity of rule-(2) first-accept against the float runs in full MDI. It stays open for FX, as it is for FA.

## 3. Engines (fixed now)
- **v14:** `ape_engine.sv` v1.4 (SHA `67367973…`), unchanged.
- **fa:** `ape_engine_fa.sv` (SHA `ada30595…`), unchanged.
- **fx2 and fx3:** a new `ape_engine_fx.sv`, in which `` `define APE_FX3 `` selects fx3. It is copied from `ape_engine_fa.sv`, with only these edits:
  1. **Thresholds.** A per-context, per-lane register `cth[A][D]`, signed, WW + 3 bits.
  2. **D2.**
     - Per lane, t = hi + lo_nz (range 0 … 2¹⁸), and θ = t − 2·diag − d2b.
     - A lane passes iff d2sw < θ. This is exactly v1.4's rule: zp < 0 always passes, zp ≥ 2¹⁸ never does, and otherwise the lane passes iff zp < hi + lo_nz.
     - A simulation assertion (`APE_FX_CHECK`, on in every run) checks (d2sw < θ) == d2_flip on every lane of every D2.
     - θ is written to `cth[d2c]`.
  3. **F2 (fx2).**
     - With the new fields `f2_wnew` and the copy's spins, a lane passes iff s·w_new < cth. Candidates are the passing lanes not in `cscan` (lanes up to m are already scanned).
     - If the flip was on the last lane, or no candidate remains, the pass ends as in FA: the scanned mask is cleared, the step advances, and the context goes to READY or OUTQ.
     - Otherwise `cpend` gets the candidates and the context stays in FLIP, so the next F1 takes the lowest candidate.
  4. **fx3.** The same compare one cycle later, in a new registered stage F3 that reads the fields already written (`cw`). This gives a shorter logic path. A flip on the last lane still ends the pass in F2. `idle_now` adds the F3 valid bit.
  5. **One test per pass.** FX never re-enters D0 within a pass, so it uses exactly one decision-port test per pass.
- **Negative controls** (D = 32, A = 1, fx2; both must fail):
  - `FX_BUG_NOMASK`: candidates are not masked with `cscan`.
  - `FX_BUG_STALE`: the compare uses the fields from before the row update.
- **Expected A = 1 cycles** per anneal, from the first D0 to OUTQ:
  - fx2: 3·S·P + 2·F.
  - fx3: 3·S·P + 3·F − F_last.
  - A constant logging offset is allowed and reported, as in A5.5 §8.
- **Register bits per context** (from the declarations; structural, not area):
  - Per lane, FA holds `cw` 24 + `crng` 32 + `cs` 6 + `cbs` 6 + three masks = 71 bits. FX adds 27 bits, for 98.
  - At A = 4, FX holds 392 bits per lane. FA holds 426 at A = 6 and 568 at A = 8, so FA at A = 6 or 8 has at least FX's register bits.
  - Not counted: FX's D threshold subtractors and D compares in the R-port path, the context muxes, and the SRAM. These are reported as structural counts only.
- **Harness.**
  - `tb_fa59.sv` and `sim_main.cpp` are unchanged; the testbench logs T at every D0, which FX hits once per pass.
  - `fx_ref510.py` is `fa_ref59.py` plus checks for modes fx2 and fx3:
    - the accepted-lane sequence equals mode 'fa' bit for bit;
    - every pass has exactly one decision-port test;
    - R-port flips equal F;
    - best spins and energy, and init ops, match;
    - at A = 1, cycles match the formulas above.
  - It also adds an A = 1 latency record per mode.

## 4. Configurations
- **Points:** the same as A5.9 §3, at the B = 1 picks, with AP as (i):
  - P1: D = 32, R = 32.
  - P2: D = 64, R = 8.
- **Stimulus:** dev seed 9600 only. Captures are reused:
  - P1: `rtl_a55/capture_9600.pt` (`cfd54514…`).
  - P2: `rtl_a59/capture_p2_9600.pt` (`0482bcd5…`).
- **Runs:** engines v14, fa, fx2 and fx3 at A ∈ {1, 4, 6, 8}, which is 32 builds and runs, plus the 2 negative controls.
- **A = 6 leaves contexts idle.** Neither R = 32 nor R = 8 divides by 6. Loads require idle, so the last round of each sub-problem leaves contexts unused. This is the engine's behaviour; it is reported, and it is why A = 8 also runs.
  - If A = 6 fails to build, or fails the checks on unchanged v14 or fa, it is dropped and reported.
- **Stage 1b, after A5.8 completes:**
  - P4: D = 128, R = 8, 64×64 at 22 dB, with A5.8's B = 1 pick if A5.8 produced one.
  - It needs one short capture on GPU0 or GPU1, done as in A5.9.
  - It is reported only and is not part of the decision rule.

## 5. Metrics
- **Cycles per anneal of a K block:** as A5.9 §4. The count runs from the block's first accepted LOAD_ROW to its last output beat, plus one, divided by 20·R.
- **Gain at equal contexts:** g_A = mean over K of cycles(fx, A) / cycles(fa, A).
- **Gain at no fewer register bits:** iso = mean over K of cycles(fx3, 4) / min over A ∈ {4, 6, 8} of cycles(fa, A).
- **Against Antiphase:** x_RTL,A = mean over K of cycles(engine, A) / cycles(v14, A), for every engine and A.
- **Held-out estimate at the existing B = 1 picks** (as A5.9):
  - x̂_A = x_F′,held × c′_A, with c′_A = x_RTL,A(fx) / x_F′,stim.
  - x_F′,stim = mean over K of (S·P + F)_FX / (L + F)_AP, from the reference's counts.
- **Latency at A = 1:** from the first D0 to OUTQ, per anneal and per engine.
- Every K is reported, together with RTL cycles over the model for each engine.

## 6. Re-costing (stage 1, CPU, read-only on `results/a55`)
- **Model F′:** cost = S·P + F_SA per anneal (one decision-port test per pass, one row update per flip).
  - x_F′ = mean over K of F′ / (L + F of (i)), with A5.5's `ref_cost` (`tuned_a52.json`).
  - The per-K flips come from each cell's saved batch counters, as in A5.5's `counts`.
- **Pool:** every rule-(2) stage-A cell at P1, P2 and P3 that has a `done.json` in `results/a55/tunea`.
  - This is A5.5's F-R pool. Cells pruned by A5.5 have x_F > 4 and therefore x_F′ > 2, so they cannot enter a budget ≤ 1.
- **Reproduction check, before any F′ number is used:** under model F, the script must reproduce A5.5's F-R budget groups (top three per budget and point, in order) in `select.json` (`f8a00cbe…`). If it does not, re-costing stops.
- **Budgets B ∈ {0.5, 1}.** Selection follows A5.5 §5 unchanged; only the cost changes:
  - The top three stage-A cells with x_F′ ≤ B go to stage B, ranked by BER, then rate of erroneous uses, then name.
  - A cell with a stage-B `done.json` already reuses it.
  - The pick is the lowest stage-B BER, with the same tie-breaks.
- **Picks with existing held-out runs:** if every cell of a group has stage B and the pick already has a seed-102 result in A5.5's `analysis.json` (a per-S or budget pick), that ratio is reported in stage 1. Otherwise the pick is a stage-2 job.
- **Disclosure:** I have seen A5.5's held-out results. No choice here depends on them, because the rule is A5.5's with only the cost model changed, and it was fixed before re-costing.

## 7. Stage 2 (GPU; separate go; after A5.8 finishes)
- **Jobs:**
  - Stage-B runs (seed 1010, A5.5 §5) for new group members.
  - Held-out runs (seed 102, A5.5 §6 stopping rule, paired with (i)) for new picks.
  - Flips (A5.5 §7) for new picks.
- **Code:** A5.5's runner and kernels, unchanged, with a separate plan under `results/a510/`.
- **Compute:**
  - hostB GPU0 and GPU1 only, through `env_hostb_a56.sh`, which checks the UUIDs.
  - A5.5's limits: at most 4 workers per GPU, 2 CPU threads each, idle-with-yield as A5.8.
- **Estimate:** at most 6 stage-B and 4 held-out cells, about 10–25 worker-hours, or 2–4 hours on 8 workers.

## 8. Decision rule (fixed now)
**Stage 1.** fx3 governs the decision; fx2 is reported as the bound if the compare fits in F2.
- **(a)** g_4(fx3) ≤ 0.80.
- **(b)** iso(fx3) ≤ 0.85.

| Outcome | Condition | Advice |
|---|---|---|
| **GO** | (a) and (b) at both P1 and P2 | Fusion leaves room for 15–20 % or more after the register overhead. Stage 2 is worth running. The author may consider a paired GF22 study of fx3 and fa at D = 64, which would reverse "Drop it" and needs its own protocol. |
| **GO-P2** | (a) and (b) at P2 only | Fusion pays at 32 users only. No GF22 unless stage 1b at P4 also meets (a) and (b); the author decides. |
| **NO-GO** | otherwise | Extra contexts, or nothing, recover what fusion offers. Advice: do not pursue fused first-accept for 18 Nov. |

- **Latency at A = 1** is reported in every outcome and does not gate. By construction it falls, to about 0.72–0.83 of FA for fx3 at these picks.
- **In every outcome:**
  - No claim about time, area, energy or clock period.
  - The paper is unchanged unless the author decides.
  - If the author pivots, the allowed wording is "RTL-simulated cycles", for a fused engine that is not synthesized.
- **Failed checks:** a failed behavioural check, a negative control that passes, or a failed reproduction check stops the affected part. The cause is reported, and no number from that part is used.

**Stage 2 terms:** as A5.5 §9 ("Antiphase leads", "SA leads", "no detected difference"), at B = 1, with x̂_4 as the cycle ratio.
- Any quote must give the point, SNR, Ns, x̂, the CI and "fused first-accept, RTL-simulated cycles, not synthesized".

## 9. Development allowance
- **FX RTL:**
  - It may be debugged on dev seed 9600 until every behavioural check passes.
  - The pipeline of §3 is fixed. After cycle numbers are seen, it changes only to fix a failed check.
  - Every fix is logged with its diff and the cycles before and after.
- **Re-cost script:** it may be debugged against the reproduction check only.

## 10. Predictions (mine, before any A5.10 code)
| Claim | P |
|---|---|
| Behavioural checks pass for fx2 and fx3 at every A and both D, and both negative controls fail | .8 |
| A = 1 cycles equal the §3 formulas (offset 0, or a constant logging offset) | .8 |
| P1 g_4(fx3) ≤ 0.80 | .5 |
| P2 g_4(fx3) ≤ 0.80 | .8 |
| P1 iso(fx3) ≤ 0.85 | .35 |
| P2 iso(fx3) ≤ 0.85 | .6 |
| Extra contexts help FA: cycles(fa, 8) < 0.9 × cycles(fa, 4) at either point | .5 |
| Outcome: GO .25, GO-P2 .3, NO-GO .45 | |
| The re-cost reproduction check passes first time | .8 |
| The P1 B = 1 pick under F′ differs from A5.5's (`abl_far_64_0.1_0.1_0_rand_32`) | .5 |
| The P2 B = 1 pick under F′ has S ≥ 64 | .7 |
| Stage 2, fused B = 1 pick: SA leads at P1 | .9 |
| Stage 2, fused B = 1 pick: SA leads at P2 | .6 |

**Reasoning:**
- The model ratios are in §2.
- At A = 4, the decision port and the R port are separate resources. FA already ran below tests + F (0.81–0.95 at P1), so some of FA's re-tests overlap other contexts' flips.
- FX removes the re-tests but changes which port binds. The realized saving may therefore fall short of the model, most at P1, where tests dominate (F/tests 0.2–0.5).

## 11. Compute
- **Stage 1:**
  - hostB CPU only, `nice -n 19`, at most 8 processes (two builds with `-j 4`, or four simulators plus references).
  - Everything goes under `<SCRATCH>/ap_ber_20261024/rtl_a510/`. `results/a55` is read only.
  - No other user's process is touched, and A5.8 is untouched.
- **Stage 1b:** one short P4 capture on GPU0 or GPU1, after A5.8 ends.
- **Stage 2:** as §7.

## 12. Not covered
- Synthesis, timing, area and energy.
- The production xorshift build. FX keeps one draw per pass, so in production it draws less often than FA.
- Full-MDI fixed-point fidelity of rule-(2) first-accept.
- Metropolis first-accept.
- Any change to Antiphase.
