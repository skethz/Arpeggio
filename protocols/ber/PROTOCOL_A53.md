# PROTOCOL A5.3: the stronger sequential SA (exploratory; not pre-registered in A5)
- **Written and frozen:** Sun 25 Oct 2026, 08:05 CET. That is before any A5.3 run and after the coordinator's go (about 07:58 CET).
- **Hash:** the SHA-256 of this file is recorded in STATUS.md and in `results/SHA256SUMS_A53.txt` on hostB.
- **Unchanged:** the frozen A5a numbers and verdicts (PROTOCOL_A5 §3). A5.3 is reported beside them.

## 1. Why
**The tie.** The A5a re-tuning pick sa2 (T0 2.4 → T1 0.0125) tied with the old SA pick (2.4 → 0.05) on seed 1000: 25 bit errors and 7 erroneous uses each. The frozen tie-break (plan order) chose sa2.

**Held-out evidence.** On seed 102 at P1 (S = 128, the same uses), sa2 has ×2.34 [1.63, 3.70] the old pick's BER (McNemar 26/3, p 1.5e-5).

**Consequence.** Sequential SA is the declared real competitor, so the paper must not understate it. A5.3 measures the old pick where A5a used sa2.

## 2. Arms
**A5.3a: Table II, x16 at Ns 64, old pick.**
- Method `abl_sa_64`: the (ix) arm, 128 sweeps, 2.4 → 0.05, from `tuned['sa']`, unchanged since PROTOCOL §4.
- Uses: seed-101 Table II uses, the same 13-point grid as A5a (16.5–22.5 dB in 0.5 dB steps), the same batch size (2,000).
- Stopping rule: ≥ 100 erroneous uses and ≥ 100 bit errors, cap 10⁷ bits.
- Reported: SNR at 10⁻³ and 10⁻⁴ by the frozen rule, with paired CIs against Antiphase Ns 64 and against sa2.

**A5.3b: P1 sweep series, old pick.**
- `abl_sao_<S>_32` for S ∈ {1, 2, 4, 8, 16, 32, 64}: the old schedule compressed over S sweeps.
- Seed 102 at P1, at least 8,000 uses, the same stopping rule.
- S = 128 is the existing (ix) arm `abl_sa_32`: same algorithm and uses, but a different solver stream.

**A5.3c: SA flip calibration.**
- Data: tuning seed 1000, batch index 50 and up, exactly as for Antiphase's φ (`calib_flips.py`).
- For both picks and every S ∈ {1, …, 128}, the mean accepted flips per anneal F_SA per sub-problem K is counted at:
  - P1: x16, 20 dB, Ns 32, 1,000 uses;
  - P2: x32, 22 dB, Ns 8, 500 uses.
- Cycles per anneal follow the A5.1 model, **S·N + F_SA**. This replaces the S·N lower bound in both sweep series, sa2 and old pick.
- The flip counter does not touch the random stream. This is tested: identical output with and without counting.

**Not in A5.3: x32 Ns 8 with the old pick.** It is estimated at more than 15 worker-hours, so its cost goes to the coordinator first.

## 3. Rule for the text (fixed now)
- Both SA arms are shown.
- **Table II text:** the stronger SA per threshold, i.e. the lower SNR at 10⁻³ and the lower at 10⁻⁴ on seed 101. This is a choice made on the test uses, and it favours SA, so it is conservative for Antiphase. It is labelled as such.
- **Sweep series:** the lower-BER pick at each S at P1. S\* is the first S whose BER-ratio CI against (i) reaches 1.
- **Cycle ratios:** quoted as (S·N + F_SA) / (L + F), per K.

## 4. Predictions (frozen)
**A5.3a.**
- Old pick: 17.9–18.6 dB at 10⁻³ and 19.4–20.7 dB at 10⁻⁴.
- Old pick minus sa2 ≤ 0 dB at both thresholds (P 0.8).
- SA minus Antiphase: −0.5 to −1.2 dB at 10⁻³ and −1.3 to −2.6 dB at 10⁻⁴.

**A5.3b.**
- Old-pick BER ≤ sa2 at every S ≥ 32 (P 0.7).
- S\* ∈ [8, 32] for the stronger series.

**A5.3c.** The accepted-flip fraction F_SA / (S·N) is:
- 0.005–0.05 at S = 128;
- 0.2–0.6 at S = 1.

So S·N understates SA's modelled cycles by ≤ 10 % at S ≥ 16.

## 5. Compute and cost
**Cost** (worker-hours):
- A5.3a ≈ 22–28. sa2's 13 points took 19.1; the old pick's lower BER sends more points to the cap.
- A5.3b ≈ 2–3.
- A5.3c ≈ 1.
- **Total ≈ 25–32.**

**Where:**
- hostB GPU1/GPU2 only while they carry no compute process outside ap_ber_20261024;
- GPU0 whenever it has ≥ 3 GB free;
- never GPU3; hostA is not used.

**Supervisor (`src/supervise_a53.sh`).**
- Workers: at most 3 (`a53g<gpu><a–c>`), each started only on a GPU with ≥ 3 GB free and no foreign process.
- Yield: every 60 s, it terminates its workers on a GPU that gains a foreign process. They resume later from saved batches; claims are reclaimed as in A5.
- CPU guard: 20 cores.
- A5 tier-1 workers are not displaced.

**ETA:** about 10–14 h wall-clock.

**Files:**
- plan: `results/plan_hostb_a53.json`;
- settings: `results/tuned_a5.json` (`sa`, `sa2`; unchanged);
- analysis: `analysis/a53.py`, output `data/a5/a53.json`.

## Addendum 1 (Sun 25 Oct 2026, 08:20 CET; coordinator's decision on x32; v1 = this file up to the line above, sha256 acdf4e61…093f)
**A5.3d: x32 at Ns 8 with the old pick, the 10⁻³ bracket only.**
- Method `abl_sa_8` at 18.5, 19.5 and 20.5 dB, on the seed-101 Table II uses, batch 1,000 (as sa2's x32 points), with the frozen stopping rule.
- Cost ≈ 16–21 worker-h.
- **Lowest priority.** It starts only after A5 tier 1 and A5.3 (a)–(c) are complete. It runs on GPUs that carry no foreign process, under the same launch and yield rules (`src/supervise_a53d.sh`), and every yield is logged.
- **The 10⁻⁴ x32 old-pick points are not run.**

**Text.** At P2 the two SA picks are indistinguishable on held-out data: sa2 at S = 128 against the old pick, ×1.16 [0.67, 2.02], McNemar p 0.85, 24k uses, measured at 08:10 CET with the job still running; the final value will be quoted. So:
- x32 at 10⁻⁴ uses sa2, labelled "possibly conservative for SA";
- x32 at 10⁻³ uses the stronger of the two per §3.

**Prediction.** At 10⁻³, old pick minus sa2 is within ±0.3 dB.

## Addendum 2 (Sun 25 Oct 2026, 17:55 CET; post hoc diagnostic, written after the A5.3 (a)/(b) results)
**Why.** The old pick's S = 128 point at P1 is the existing (ix) run `abl_sa_32`, at ×0.30 against (i). Its own S = 64 point (`abl_sao_64_32`) is ×0.73, sa2 plateaus at ×0.57–0.59 for S = 64 and 128, and on Table II x16 Ns 64 the two picks are indistinguishable. So it is unclear whether ×0.30 is reproducible.

**Diagnostic.** One replicate, `abl_sao_128_32`:
- the same algorithm, schedule and seed-102 uses as `abl_sa_32`;
- only the solver random stream differs, because it hashes the method name;
- at least 8,000 uses, the frozen stopping rule, about 1 worker-hour;
- launch and yield rules as in A5.3.

**Use.** It decides which SA is stronger at S = 128 at P1. Both runs are reported. It does not change the Table II rule (§3).
