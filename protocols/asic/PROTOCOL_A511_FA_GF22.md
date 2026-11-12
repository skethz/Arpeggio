# PROTOCOL A5.11 — first-accept SA through the Antiphase GF22 flow (TT, post-route)

Written and frozen 7 Nov 2026 before any tool ran on a first-accept design. The user's go was "work it out yourself so it finishes as fast as possible" (7 Nov, about 05:55 CET); this reopens the GF22 first-accept engine that was dropped earlier that day.

## 1. Question
All three v12 reviews name the same top weakness: only Antiphase is routed, and first-accept SA is RTL-simulated only.

At the A5.5 B = 1 picks, first-accept SA has fewer RTL cycles than Antiphase at A = 4 (A5.9: x̂ = 0.856 at P1, 0.678 at P2) and equal or lower BER. Does that lead survive the physical cost of its select and re-test logic, that is, its clock, area and power?

## 2. Designs (frozen inputs)
- **First-accept:** `ape_engine_fa.sv`, SHA-256 `ada3059e94fd…` (A5.5/A5.9 file, unchanged).
  - Production build: no `APE_PHILOX`, no `APE_FA_BAL`, no `FA_BUG_NOMASK`. Both picks use random starts and q = 0.
  - Module name `ape_engine`, with the same ports, memories and parameters as v1.4.
- **Antiphase control:** `ape_engine.sv` v1.4, `67367973dd0b…`. These are the accepted routed DBs `ape_d32_p1150_r4` (1.15 ns) and `ape_d64_r4` (1.00 ns). They are used unchanged, except for the new like-for-like activity in §4.
- **Instances:** D = 32, A = 4, SEEDL = 1 (P1); D = 64, A = 4, SEEDL = 2 (P2).
- **Synthesis:** `flow/syn_generic.tcl` and `run_syn.sh`, exactly as v14.
  - SYN_TOP `ape_engine`; files are the same memory wrapper plus the engine file; parameters D/A/SEEDL as above.
  - The same two macros; period 1000 ps; 6 CPUs; effort medium; TT.
- **Place and route:** `flow_v2_20261024/run_v2.sh` and `pnr_v2.tcl` with body rev4, as the accepted Antiphase runs.
  - Utilisation 0.60 (back-solved from the r4 floorplans: D64 std 128,729 µm² / logic 214,547 µm² = 0.600).
  - 8 CPUs, stop `final`, the same macro lists, TT.

## 3. Clock walk (the Antiphase rule)
- One P&R at the synthesis SDC (1.00 ns).
- If setup misses, rerun at T + |WNS| rounded up to 50 ps (`sdc_scale.py`, same version). This repeats until a run passes.
- Runs at 1.05, 1.10 and 1.15 ns may be pre-staged to save time. They count only where the rule reaches them; a pre-staged run never counts by itself.
- **Acceptance:** all of these must hold.
  - TT setup WNS ≥ 0 in every path group and hold WNS ≥ 0;
  - DRC 0;
  - connectivity 0 opens;
  - placement legal;
  - FLOW_V2_DONE_FINAL.
- A run hung for more than 3 h in one step is killed, kept as `_hung`, and relaunched once.
- **T_AP** is the accepted Antiphase period at the same D: D32 1.15 ns, D64 1.00 ns.

## 4. Activity and power (like-for-like)
- **Stimuli:** the A5.9 streams (dev seed 9600, both engines on the same captured sub-problems).
  - `stim_p1fa` / `stim_p1ap` (D32, R = 32);
  - `stim_p2fa` / `stim_p2ap` (D64, R = 8).
- **Simulation:** Questa 2025.3 runs the production build of each engine with `tb/tb_ape.sv` (the same reader).
  - Pass 1, without SAIF, gives TS, the acceptance cycle of the first command with op ≠ 3 (the first after the schedule-table load), and TE, the last cycle.
  - Pass 2 writes the windowed SAIF over [TS, TE] with `flow/saif_window.py`, as `tb/run_saif.sh` does.
  - Both passes run at the engine's accepted period.
- **Power:**
  - Genus reads each SAIF on that engine's synthesis DB and writes a TCF (`flow/power_saif.tcl`).
  - Innovus TT power runs on each routed DB with its TCF (`flow/run_power.sh` method).
  - Antiphase is re-annotated with the stimuli above on its existing routed DBs, so both engines use one stimulus source.
- **Functional checks:**
  - Every production run must finish all commands with the expected number of output beats.
  - Conformal LEC (RTL → syn → routed, project dofiles) runs on first-accept as gate item G3. It is reported and does not block the ratios.
  - No bit-exact model exists for first-accept with xorshift. A5.5/A5.9 established bit-exact behaviour with Philox; the RNG code is the same file as v1.4.

## 5. Metrics
At each point, for each engine:
- accepted period T;
- die, core, std-cell and macro area;
- total power P;
- energy per cycle e = P·T.

**Primary ratios (first-accept / Antiphase):**
- time per detection: **ρ_t = x̂_A4 · T_FA / T_AP**;
- energy per detection: **ρ_E = x̂_A4 · e_FA / e_AP**.
- x̂_A4 is fixed from A5.9: 0.856 at P1, 0.678 at P2.

**Check:** the same ratios with the production-run cycle ratio C_FA/C_AP from pass 1.

**Also reported:**
- area ratio;
- ρ_t at the break-even of §6;
- slow-corner clock, only if time allows (not primary).

## 6. Decision rule and predictions (frozen)
**Decision rule**, at each point separately:
- **ρ_t ≤ 1 and ρ_E ≤ 1:** "first-accept also leads in routed time and energy per detection".
- **Both > 1:** "Antiphase leads physically despite more cycles".
- **Otherwise:** a mixed result, reported as measured.

Break-even, from x̂ alone: T_FA/T_AP ≤ 1.168 at P1 and ≤ 1.475 at P2.

**Predictions.** The first-accept delta is a per-context scanned-lane mask (A·D flops: 128 at D32, 256 at D64), an AND in front of the existing lowest-bit encoder, and a return to D0.
- The same accepted period as Antiphase, or within one 50 ps step.
- Std-cell area within +5%.
- e within ±10%.
- So ρ_t ≈ 0.86 / 0.68 and ρ_E ≈ 0.8–0.95 / 0.6–0.75: **first-accept leads at both points**.

**Paper:**
- The III-C sentence becomes the measured result.
- Any other change (abstract, Table IV row, framing) is the user's call.
- No change is made without the user's go.

## 7. Compute and safety
- **hostB:** CPU only, at most 24 threads for this work. A5.8 keeps GPU0-1 and its 8 workers. Our jobs run at `nice -n 10`.
- **hostD:** at most 24 threads for the pre-staged clock runs and the power/LEC jobs.
- All files live in `<SCRATCH>/antiphase_asic_20261017/` (the same absolute layout as hostE/12, so scripts run unchanged) plus `…/fa_a511/`.
- HOME and XDG for tools point under that folder. Nothing goes in `<HOME>`.
- Kit-derived files are copied only server to server, never through the Mac.
- Other users' processes and the user's own running jobs are never touched.
- **Stop rule:** if no D64 period is accepted by 10 Nov 18:00 CET, stop and keep the current limitation text.

## 8. Not in scope
- the comparator-reusing dilution controller (new RTL);
- new BER runs;
- 64 users.
