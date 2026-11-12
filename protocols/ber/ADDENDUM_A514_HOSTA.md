# Addendum to PROTOCOL_A514.md: P4 W = 4 overflow to hostA GPU5 (compute only)

**Written:** 10 Nov 2026, about 08:10 CET, before any hostA batch (gate or held-out).
**Go:** author, 10 Nov 2026, about 08:00 CET: "<instruction>" (after I reported that hostA GPU5 was free and that this session used no hostA GPU).
**Nothing in sections 1–9 changes:** questions, arms, S rules, seeds, estimators, decision and outcome table stay as frozen.

## What moves
- **Jobs:** A5.14 P4 W = 4 (`abl_faw_4_60_0.1_0.1_0_bal_8`, seed 344, batches 0–599, 150 chunks of 4 batches), last in hostB's queue.
- **Order on hostA:** from the last chunk backward (c149, c148, …).
- **hostB's plan.json** drops these chunks. Its workers re-read the plan before every job, so none starts them.
- **Rebalancing:** by throughput only. Unclaimed chunks may move back to hostB later (removed from hostA's plan first). No result is read for this.
- **Results:** hostA batches are copied into hostB's `results/a514/a514_cNNN/x64/abl_faw_4_60_0.1_0.1_0_bal_8/snr_22.00/`, with the same file names. Each batch's info records its host and GPU.

## Compute
- hostA GPU5 only (`env_hosta_a514.sh` sets its UUID).
- Untimed; no timing or energy from this run.
- Idle-with-yield: our workers stop if any other compute process appears on GPU5. nice 10.
- At most 6 workers with 2 threads each.
- Code: hostB's `src/` and `code_mimo/src/`, copied byte for byte (hashes compared). Same torch 2.11.0+cu128 and numpy 2.5.4.

## Host gate HZ (before any held-out hostA batch)
- **HZ1:** hostA reruns A5.8's saved P4 W = 1 batch 0 (seed 344, `abl_far_64_0.1_0.1_0_bal_8`) and compares per-use bit errors and x̂ with the saved file.
- **HZ2:** P4 W = 4 at S 60 on dev seed 9600, batch 0 (500 uses), on both hosts; same comparison.
- **Pass:** in each, at most 0.5% of uses differ in per-use bit errors (the G4 bound).
- **Fail:** no held-out batch runs on hostA, and the jobs return to hostB.

## Analysis
Unchanged: analyze_a514.py pairs by global batch index. Because the W = 4 arm at P4 then spans two hosts, the host-gate rates are reported with the result.
