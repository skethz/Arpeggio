# PROTOCOL A5.19: confirmatory re-tests at 64 users (re-tuned Chord) and 16 users (replication), fresh seed 2028

**Status:** draft 13 Nov 2026, 18:05 CET. Frozen when `results/a519/SHA256SUMS_A519.txt` is written on hostB, before any job of the supervisor (stage A included) runs.
**Go:** author, 13 Nov 2026: "Text + confirmatory runs" (remedy B of `<PROJECT>/work/review_blind_20261113g/README.md`, weakness 4: headline Arpeggio results exploratory, Chord tuned only at 16 and 32 users), then "<instruction>".
**Paper:** unchanged. Nothing from this run enters main.tex without the author's go.

## 1. Questions
- **Q1 (primary).** At P4 (64×64 16-QAM, 22 dB, N_s = 8), given re-tuned Chord's modeled cycles, does Arpeggio have a different BER from re-tuned Chord?
- **Q2 (secondary).** The paper's 64-user Arpeggio (`abl_far_64_0.1_0.1_0_bal_8`, A5.8's B = 1 pick) against default Chord on a fresh seed: the replication of 0.78× [0.72, 0.85] (seed 344, exploratory).
- **Q3 (secondary).** Re-tuned Chord against default Chord at P4.
- **Q4 (secondary).** At P1 (16×16 16-QAM, 20 dB, N_s = 32), the paper's Arpeggio (`abl_far_64_0.1_0.1_0_rand_32`) against default Chord (`mdiane32`, which A5.5's re-tune kept at P1) on a fresh seed: the replication of 0.46× [0.30, 0.67] (seed 102, exploratory).
- Also reported: A*/C0 and A*/A64 at P4.

## 2. Arms (float, same draws within a point)
| Point | Arm | Method | Note |
|---|---|---|---|
| P4 | C0 | `a56_128_0.3_0.3_0.4_0_alt_8`, stream `mdiane8` | default Chord, as X64F and Table IV's float reference |
| P4 | C64 | `abl_ape_<T0>_<T1>_<q>_<st>_8` | re-tuned Chord (section 3) |
| P4 | A* | `abl_far_<S*>_0.1_0.1_0_bal_8` | Arpeggio at C64's cycles (section 4) |
| P4 | A64 | `abl_far_64_0.1_0.1_0_bal_8` | the paper's 64-user Arpeggio |
| P1 | C0 | `mdiane32` | default Chord = A5.5's re-tuned pick at P1 |
| P1 | A16 | `abl_far_64_0.1_0.1_0_rand_32` | the paper's 16-user Arpeggio |

All arms run through `src/trace_a514.py` (trace_a56.py with x64 and apx514 registered; unchanged since A5.14). Draws `apx.draw(seed, snr, bi, B, nt, M)`; solver streams as the runner (draw seed + 7919 + mhash(stream)).

## 3. Chord re-tune at P4 (tuning seeds 1000 and 1010 only), as A5.5 section 5
- **Grid:** A5.5's Chord grid, q ∈ {0, 0.1, 0.2, 0.4, 0.8} × constant T ∈ {0.1, 0.15, 0.2, 0.3, 0.5}, plus (T0, T1) ∈ {(0.6, 0.2), (0.6, 0.1), (1.2, 0.2)} × q ∈ {0.2, 0.4}: 31 cells, each with `rand` and `bal` starts (62 cells). L = 128·P as Chord; the grid contains default Chord's setting (0.3, 0.3, 0.4, rand).
- **Stage A:** seed 1000, 8 batches of 500 (4,000 uses), flips counted.
- **Corners:** as A5.5: the stage-A best on a grid edge adds the next cell beyond that edge, start and other settings held; at most two rounds; a best still on an edge is reported.
- **Stage B:** the three stage-A cells with the lowest BER (ties: rate of erroneous uses, then method name) on seed 1010, batches of 500, until ≥ 30 erroneous uses or a cap of 20,000 uses. **C64** = lowest stage-B BER, same ties.
- No cycle budget: Chord's re-tune is free to use more or fewer cycles, as at P2 (A5.5).

## 4. S* (fixed before any held-out batch of A*)
- **Calibration:** tuning seed 1000, batch index 50, 500 uses, through the same worker (solver stream from the method name). Cost x = mean over K of (tests or half-steps + flips) per anneal over default Chord's L_K + F_K on seed 1000 (A5.8 `ref_cost`: 379.29 / 893.48 / 2,038.75).
- **Arpeggio family:** rule (2), constant T = 0.1, q = 0, `bal` start (the A5.8 B = 1 pick's family, and A5.8's stage-A best at S = 128).
- **Rule:** S* is the largest S on the grid {96, 104, …, 176} with x(S) ≤ x(C64), both calibrated on the same batch. If x(176) ≤ x(C64), the grid extends upward in steps of 8; if x(96) > x(C64), downward in steps of 8 (down to 8). Same as A5.15 section 3, with step 8.
- If S* = 64, A* and A64 are the same arm.

## 5. Held-out run
- **Seed 2028:** never used on hostB (checked 13 Nov over every done.json: seeds 101, 102, 104, 105, 344, 1000, 1010, 1020, 2027, 9100, 9600) or in any local record.
- **P4:** batch indices 0–599 of 500 uses (300,000 paired uses per arm), chunks of 10 batches. **P1:** batch indices 0–149 of 2,000 uses (300,000 paired uses per arm), chunks of 10 batches. Fixed in advance; no early stopping.
- **Order:** tuning jobs first, then calibration, then held-out chunks interleaved across all arms by fraction of the run, so the arms progress together. C0, A64 and both P1 arms are queued at launch; C64 and A* when their picks exist.
- **Time cut: 16 Nov 2026, 12:00 CET.** If not complete by then, each comparison uses the batch indices completed by both of its arms, and x_F those completed by the arm and C0. Which batches complete depends on the queue, not on results. No held-out result is looked at before the analysis runs; the author may move the cut later only before then.

## 6. Estimators
- BER ratio = Σ bit errors (arm) / Σ bit errors (reference), over the same uses.
- 95% CI: paired bootstrap over uses, `a56an.boot_ratio` (4,000 replicates, seed 12345). Exact McNemar on uses with an error in exactly one arm (`a56an.mcnemar`).
- **Terms:** "Arpeggio leads" if the upper bound < 1; "Chord leads" if the lower bound > 1; otherwise "no detected difference" (C64/C0: "re-tuned leads" / "default leads").
- Reported for each arm: uses, bit errors, erroneous uses, BER, held-out cycles per K, x (over A5.8's ref_cost) and x_F (over C0's own held-out cost, P4).

## 7. Analysis (`src/analyze_a519.py`, written before any A5.19 run)
- **Primary:** A*/C64 at P4. The only confirmatory comparison at P4.
- **Secondary (reported as such, no correction):** A64/C0, C64/C0, A*/C0, A*/A64 at P4; A16/C0 at P1 (the confirmatory replication of the 16-user claim).
- A check, not a decision: if A*'s held-out cycles exceed C64's by more than 2% (both over A5.8's ref_cost, on the primary's batch indices), that is reported next to the primary.
- **Partial run.** A comparison with fewer batch indices than planned (time cut) is flagged partial and reported with its uses. A partial replication (A64/C0, A16/C0) whose CI contains both 1 and the earlier estimate (0.783, seed 344; 0.464, seed 102) is "inconclusive (partial run)", not "no detected difference": too small to tell the two apart.

## 8. Predictions (written before any A5.19 run; my estimates)
- C64 differs from default Chord's setting: p = .7. x(C64) in [0.8, 1.3]: p = .8.
- S* in 96–168: p = .75 (A5.8 stage A: x = 0.561 at S = 64, 1.007 at S = 128 for this family).
- A*/C64 about 0.65; "Arpeggio leads": p = .75.
- A64/C0 about 0.82; "Arpeggio leads": p = .75.
- C64/C0 about 0.85; "re-tuned leads": p = .5.
- A*/A64: "A* leads": p = .85.
- A16/C0 (P1) about 0.6; "Arpeggio leads": p = .9.

## 9. Outcome → text (frozen)
Every use needs the author's go. These runs are pre-registered (this protocol) and on a fresh seed, so the text may call them confirmatory.

| Primary A*/C64 (P4) | What the text may say |
|---|---|
| Arpeggio leads | "At 64 users, given re-tuned Chord's cycles (x×), Arpeggio has r× [lo, hi] its BER (pre-registered, fresh seed)." With A5.15, the abstract may say Arpeggio beats re-tuned Chord at 32 and 64 users at no more cycles. It must stay stated that A* uses S* sweeps, more than the B = 1 pick's 64. |
| No detected difference | "At 64 users, at re-tuned Chord's cycles, Arpeggio and re-tuned Chord do not differ (r× [lo, hi])." The 64-user claim stays against default Chord only. |
| Chord leads | "At 64 users, re-tuned Chord leads Arpeggio at equal cycles (r× [lo, hi])." Any 64-user "beats Chord" must name default Chord; the claim set changes, so the author decides the wording. |

| Secondary | What the text may say |
|---|---|
| A64/C0 Arpeggio leads | The 64-user result may be called replicated: "0.78× [0.72, 0.85] (seed 344), r× [lo, hi] on a pre-registered fresh seed". |
| A64/C0 no detected difference | Must be reported: "on a second, pre-registered seed, no detected difference (r× [lo, hi])"; "beats default Chord at 64 users" must be qualified or removed (author). |
| A64/C0 Chord leads | Must be reported; the 64-user claim against default Chord is withdrawn (author decides the wording). |
| C64/C0 | May be printed: "re-tuned Chord at 64 users: r× [lo, hi] at x×". Chord is then re-tuned at 16, 32 and 64 users. |
| A16/C0 Arpeggio leads | The 16-user result may be called replicated: "r× [lo, hi] on a pre-registered fresh seed". |
| A16/C0 no detected difference or Chord leads | Must be reported; "beats Chord at 16 users" must be qualified or withdrawn (author). |

| A64/C0 or A16/C0 "inconclusive (partial run)" | Reported with its uses and CI as a partial run; the existing statement (seed 344 or 102) stays, and the text may not call it replicated. Any other partial comparison follows its row above, with its uses stated. |

**May not say:** any timing, energy or area from these runs (5090s, untimed); that A* is the paper's B = 1 pick; any pooling of seeds 344 / 102 with seed 2028 chosen after seeing results.

## 10. Compute and files
- hostB GPU0–3 (standing allocation, 11 Nov), UUIDs enforced by `env_hostb_a519.sh`. Shared with the author's running jobs at the author's request ("queue"): no yield, but a memory guard (`supervise_a519.sh`) that leaves room for the author's next queued job (about 6 GB): no new worker on a GPU with < 9,000 MiB free (a 64-user worker takes about 3,700 MiB); below 2,500 MiB free our newest worker there is stopped (it resumes from saved batches). Other processes are never touched.
- At most 3 workers per GPU (12), as memory allows, 2 threads each, nice 10, 20% memory cap each; with the running LEC job and the author's processes, <USER> stays within the 24-core cap.
- Outputs: `<SCRATCH>/ap_ber_20261024/results/a519/<set>/<shape>/<method>/snr_<snr>/bNNNNN.npz`; select.json and plan.json there; logs `logs/a519/`.
- Code and inputs hashed in `results/a519/SHA256SUMS_A519.txt`; local copies in `code_a519/`.
- A job that fails 3 times is left for inspection. Failed or diverged jobs are analysed and re-run as dated amendments.

## 11. Checks before freezing (13 Nov 2026, hostB GPU0-3 shared with the author's jobs)
- **Amendment before the freeze (13 Nov, after the gates, before any A5.19 job):** the gates showed A64 at 8,833 s per batch while sharing, so the run will end at the time cut. The analysis now pairs each comparison on its own batch indices (it had used only the indices all four P4 arms share, which the slowest arm would set) and adds the partial-run rule (sections 5, 7, 9). Nothing else changed.
- **SIM PASS** (`sim_a519_plan.py`, synthetic results, no GPU; re-run after the amendment, with a partial-run case: A* batches 0-36, A64 the first 5 of each chunk, A16 batches 0-19) at three re-tuned-Chord costs: x(C64) = 1.40 (grid extends upward to 184, S* = 176), 0.60 (extends downward to 64, A* = A64), 1.05 (S* = 128, no extension). Checked: 62 stage-A cells first, then stage B (seed 1010), calibration (seed 1000, batch 50), held-out (seed 2028); no C64/A* chunk before its pick; every P4 arm covers batches 0-599 and every P1 arm 0-149; the analysis pairs all batches.
- **Replay gates** (`results/a519_gate/`, worker `trace_a514.py`, one batch each, `saved` = the stored batch):
  - G1 `abl_ape_0.3_0.3_0.4_rand_8` with stream `mdiane8` against X64F batch 0 (seed 344): identical. X64F batch 0 has no erroneous use, so the bit-error check alone is weak; the flip counters are the strong check: flips per K 2,795,809 / 3,310,223 / 2,125,575 over 22,908 / 8,542 / 1,694 anneals, identical to X64F's saved counters. The re-tune grid's (0.3, 0.3, 0.4, rand) cell is default Chord's trajectory.
  - G2 C0 (`a56_128_0.3_0.3_0.4_0_alt_8`, stream `mdiane8`) against X64F batch 0: identical, same counters.
  - G4 `mdiane32` against seed-102 batch 0 at P1 (8 erroneous uses): identical.
  - G3 A64 against A5.8 held0 batch 0 (seed 344, 1 erroneous use, 37 bit errors): identical bit errors, and identical counters (flips 296,127 / 638,077 / 1,052,811, tests 3,231,861 / 2,814,104 / 1,670,304 over 22,956 / 8,520 / 1,630 anneals).
  - G5 A16 against A5.5 seed-102 batch 0 at P1 (5 erroneous uses, 31 bit errors): identical bit errors. The A5.5 batch predates the counters, so only the bit errors are compared.
- **Speed while sharing with the author's jobs:** C0 at P4 437-854 s per 500 uses (A5.8: 75 s), `mdiane32` 324 s per 2,000 uses (A5.5: 27 s), A64 8,833 s per 500 uses (G3, 18:01-20:29; A5.8: 390 s), A16 5,131 s per 2,000 uses (G5). About 6-23x slower than A5.8/A5.5: the author's processes keep each GPU busy and our small kernels wait for time slices. At this speed the run will not finish before the time cut; section 5's cut then applies unchanged. Recorded before the freeze; no rule changed.
