# PROTOCOL A5.4: Antiphase schedule-length series (exploratory; not pre-registered in A5)
- **Written and frozen:** Wed 4 Nov 2026, before any A5.4 run and after the author's go in chat ("<instruction>", then "<instruction>").
- **Hash:** the SHA-256 of this file is recorded in STATUS.md and in `results/a54/SHA256SUMS_A54.txt` on hostB.
- **Unchanged:** every A5 and A5.3 number and verdict. A5.4 is reported beside them and is labelled exploratory wherever it appears.

## 1. Why
Fig. 3(a,b) gives sequential SA a budget series, S = 1…128 sweeps, up to 29–33× (P1) and 46–57× (P2) of Antiphase's modeled cycles, but Antiphase only its frozen schedule L = 128·P. PROTOCOL_A5 did not ask for an Antiphase series. So the figure cannot say whether SA's lower BER at long budgets survives when Antiphase gets the same cycles.

**Question:** how does Antiphase's BER change with schedule length, and how does it compare with SA at about equal modeled cycles?

## 2. Arm
`abl_anel_<Sk>_<Ns>`: the same call as (i) `mdiane<Ns>`, `mimo.anechoic(I, na, Sk·2K, 0.3, 0.3, 0.4, kappa=0, phases=2K)`, so L = Sk·P half-steps.
- Frozen T 0.3 and q 0.4; no re-tuning at any Sk. SA's series likewise compresses one frozen pick. A longer schedule might prefer other settings, which this does not test.
- MDI wrapper, Ns and random start unchanged.
- **Grid:** Sk ∈ {32, 64, 128, 256, 512, 1024, 2048, 4096} at P1 (x16, 20 dB, Ns 32) and P2 (x32, 22 dB, Ns 8); Sk = 8192 at P2 only, last in the plan.
- **Sk = 128 is a stream control.** The solver stream depends on the method name, so `abl_anel_128_*` is the same algorithm as (i) on the same draws with different solver random numbers. (i) stays the reference.
- **Uses:** seed 102, the draws of (i), batch 2,000 / 1,000. Stopping rule as PROTOCOL §3.4: ≥ 100 erroneous uses and ≥ 100 bit errors, minimum uses 8,000 / 4,000, cap 10⁷ bits.
- **Code:** `src/runner_a54.py` adds this one method name and runs `src/runner.py` unchanged. `apx.py`, `runner.py` and `mimo.py` are not edited. Results go under `results/a54/`, so no existing file can be touched.

## 3. Flip calibration
Modeled cycles per anneal stay L + F (PROTOCOL_A5 §1). F is measured per Sk and K on tuning seed 1000 only, as `calib_flips.py`: batch index 50, 2,000 uses at P1, 1,000 at P2, solver seed 1000, `apx.anechoic_colour` with m = 1 (`src/calib_flips_a54.py`). At Sk = 128 it must reproduce `results/a5_flip_phi.json` exactly; if not, the cycle axis stops here until explained.

## 4. Reported, and the rule for the text (fixed now)
**Comparison series,** as Fig. 3 draws them: P1 old pick (`abl_sao_<S>_32`, S = 128 `abl_sa_32`); P2 frozen sa2 (`abl_sas_<S>_8`).

**Reported:**
- BER and the ratio to (i) per Sk, paired 95 % cluster-bootstrap CI over channel uses, McNemar, as in A5.
- Cycle ratio (L + F)/(L₁₂₈ + F₁₂₈) per K.
- For each S ≥ 4, the Sk whose mean cycle ratio over K = 1–3 is nearest SA's on a log scale, with the paired Antiphase/SA BER ratio on common uses.

**Wording:**
- "Saturates at Sk" means the next two doublings both have ratio CIs that cover 1.
- "Antiphase wins at equal modeled cycles through X" needs the CI of the paired ratio to exclude 1 below 1 at every matched budget up to X, stated per point.
- "Longer sequential SA buys lower BER" stays in the paper only if, at the largest matched budget at that point, the CI excludes 1 in SA's favour. Otherwise the figure title and the sentence change.
- The result is reported whichever way it falls. No re-tuning or extra arm is added to change it.

**Fig. 3:** if used, the Antiphase star remains at (1,1) as (i) and the series is drawn through it. Whether the paper uses A5.4 at all is the author's decision.

## 5. Compute
- **hostB GPU0 and GPU1 only** (author, 4 Nov 2026): `<GPU_UUID>`, `<GPU_UUID>`. `env_hostb_a54.sh` refuses any other GPU. Untimed; no timing is ever reported from this amendment.
- At most 3 workers per GPU plus one calibration process, 2 CPU threads each, each capped at 30 % of GPU memory.
- **Sharing:** the author allows another user's job on the same GPU, so workers do not yield to it. The supervisor launches nothing on a GPU with < 8 GB free and stops one of our workers if free memory falls below 2 GB; that worker resumes from saved batches. It never touches another user's process.
- A job that fails 3 times is left for inspection and logged.

## 6. Checks before freezing (dev seed 1000; saved held-out batches already reported)
- `src/test_a54.py`, ALL PASS: `abl_anel_128_<Ns>` is bit-identical to `mdiane<Ns>` for the same solver seed at x16 and x32; Sk = 64 changes the anneal count and returns constellation levels.
- `src/replay_a54.py`, ALL IDENTICAL on all four 5090s: batches 0–1 of (i) at P1 and P2 recomputed with the runner's seeds. Per-use bit errors and every erroneous x̂ match the saved arrays bit for bit, 16 of 16 comparisons, including on GPU2 and GPU3 with four processes of another user's job on the same GPU (utilization up to 97 %). Sharing changes speed, not results.

## 7. Cost
Rates from the replay with no other job on the GPU and one worker: about 125 uses/s at P1 and 41 uses/s at P2 at Sk = 128, scaling as 1/Sk. If every long job reaches the bit cap: about 19 worker-hours at P1 and 33 at P2 through Sk = 4096, plus 35 for Sk = 8192 at P2, longer with several workers on one GPU. The longest single job sets the wall clock, since a job is not split between workers.
