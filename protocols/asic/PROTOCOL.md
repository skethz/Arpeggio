# Antiphase ASIC gate G2–G5 on the flow-v2 rev4 engines: equivalence, activity power, slow-corner clock, fairness

Written and frozen **2026-10-24 22:26 UTC (Sun 25 Oct 00:26 CEST)**, before any equivalence, power or corner-timing
result of this work exists. The time is the save time; the sha256 is in `PROTOCOL.sha256` and on both servers. The
predictions (§8) are not revised after any result is read. Gate items: `reviews_20261024/antiphase_META_chair.md` §6.5 as
adapted by `plan_20261024/antiphase_framing/FRAMING_B_on_A.md` §5 (no AHC engine; comparator = PIMI's released RTL).

Server work directory **`A/gate_r4_20261024T2220Z/`** on hostC (LEC, STA) and the directory of the same name on hostD
(power), A = `<SCRATCH>/antiphase_asic_20261017`. Kit data, library/cell/macro names, private reports and
per-instance data stay there; only aggregates come to the laptop.

## 1. Designs under test (read-only)
| Engine | Routed DB (flow v2 rev4) | Accepted clock (TT) | Synthesis it was built from | Top |
|---|---|---|---|---|
| D32 | `A/flow_v2_20261024/ape_d32_p1150_r4` | 1.15 ns (setup +2, hold +27 ps) | `A/ape/syn/v14_d32_p1000` (netlist sha256 751799bf…) | ape_engine_D32_A4_SEEDL1 |
| D64 | `A/flow_v2_20261024/ape_d64_r4` | 1.00 ns (+4 / +21 ps) | `A/ape/syn/v14_d64_p1000` (a51de72d…) | ape_engine_D64_A4_SEEDL2 |
| D128 | `ape_d128_p1050_r4` (running) | 1.05 ns if it closes | `v14_d128_p1000` (8750de27…) | ape_engine_D128_A4_SEEDL4 |
| PIMI (their HLS RTL, J banks as macros) | hostD `pimi_hls_r4b` (routing) | 1.0 ns if it closes | `A/pimi/syn/m1000` (0d024f16…) | pbits_anneal |

The accepted run directories are never modified or re-saved. Every tool session restores into a new output directory; the
launcher re-binds the accepted directories read-only inside bwrap. No P&R, ECO or synthesis. If anything needs a layout
change, the work stops and is reported.

**RTL:** `ape_engine.sv` v1.4 (sha256 67367973…eacb, identical to both synthesis snapshots) + the server-only macro wrapper
`ape_mem_gf22.sv` (6f08dcb7…), copied from hostE with hashes (`inputs/SRC.sha256`, 116 files).

## 2. Activity provenance (established before freezing; read-only checks)
The existing TCFs `A/ape/tcf/P{1,2,3,4m,4s}_TT.tcf` (hostC) are byte-identical (sha256) to the Genus outputs
`v14_d{32,64}_p1000/power_final/*_TT_netlist.tcf` on hostE. Chain, all hashes checked:
- RTL v1.4 (67367973…), production RNG, Questa testbench `tb_ape.sv` (ea886b22…), `run_saif.sh` (87e81552…), simulated at
  1,000 ps (`run_final_saif.sh`, tag fin14); SAIF windowed after the one-time schedule-table load to the last cycle.
- Streams = real MDI detection streams (command replay) of the ASIC draws fixed in PROTOCOL_ASIC before any result. These
  draws are disjoint from the tuning set (seed 1000), i.e. held out:
  P1 = x16 20 dB, MDI Ns 32, seed 41, first 12 detections (696,729-cycle window); P4m = x16 31.02 dB MDI Ns 8, seed 45,
  400 detections (313,264); P4s = x16 31.02 dB one stage R 4, seed 45, 200 detections (247,715); P3 = q32 14 dB DI Ns 8,
  seed 43, 60 detections (152,300); P2 = x32 22 dB MDI Ns 8, seed 42, 12 detections (267,682).
  Every RTL run printed `SUMMARY PASS` (outputs and output cycles equal to the cycle-exact model).
- Genus 25.11 read each SAIF on the **same synthesis database** whose `out/netlist.v` the r4 layouts read (the r4 stdout logs
  read exactly `A/ape/syn/v14_d{32,64}_p1000/out/netlist.v`, hash-identical to hostE) and wrote `write_tcf -computed
  -hierarchical`, top scope filled in. Genus asserted 99.99 % (D32, P1) / 99.19 % (D64, P3) of flops from the SAIF; ICG
  outputs and combinational nets are Joules-computed.
- **Verdict: source-matched** (same RTL, same netlist, real held-out streams). They are used; no regeneration is needed.
- **Only mismatch: clock.** The TCFs encode 1.000 ns activity (duration 1e9 ns, clock port 2e9 toggles). D64 is accepted at
  1.00 ns (used unchanged). D32 is accepted at 1.15 ns: its TCFs are rescaled in time by K = 1.15 by changing **only the
  duration token** (1e09 → 1.15e09); every toggle count and duty is byte-identical (energy per cycle fixed; exact for a
  zero-delay cycle-based RTL activity; precedent: an earlier project r4 K = 5 rescale and the 18 Oct duration-token audit). Checked by a
  byte diff (one line differs) and by Innovus' reported clock toggle rate (= 1/1.15 ns). D128 at 1.05 ns: K = 1.05.
- PIMI: `A/pimi/syn/m1000/reports/F_pw_p4_netlist.tcf` (P4 stream, 1 GHz, duration 1e9 ns). Its provenance (RTL, netlist,
  stream) is checked the same way before it is used; if it is not source-matched to `m1000/out/netlist.v`, it is
  regenerated from RTL simulation of the stream and that is logged as an amendment.

## 3. G3 function: equivalence chain (Conformal 25.10, LEC -XL), per engine
1. **RTL → fv_map → synthesis netlist:** the composite dofile written by Genus `write_do_lec -revised_design <netlist.v>`
   from the restored synthesis database (read_db only, no synthesis), with only its log paths and RTL file paths redirected
   to the hash-identical gate copies. If Genus cannot write it, fallback: Genus' existing `fv/<top>/rtl_to_fv_map.do`
   (RTL → fv_map, hierarchical) + a project-authored flat fv_map → netlist compare (logged as an amendment).
2. **Synthesis netlist → final routed netlist** (`final_netlist_private.v`): project-authored flat compare as an earlier project's
   (golden = syn netlist, revised = routed netlist, TT std-cell liberty; tie cells as constants; physical-only cells absent or
   excluded; key points mapped by name; all compare points).
- **Macros** (G-memory and schedule-table register files) are black boxes on both sides (`add_notranslate_modules`,
  as Genus' dofile does); their pins must map one-to-one (`report_black_box`, unmapped-point report).
- Report per stage: Equivalent / non-equivalent / aborted / not-compared counts, black boxes, unmapped points.
  **Gate:** 0 non-equivalent, 0 aborted, 0 not-compared key points other than documented unreachable ones.
- The RTL is bit-exact with the cycle reference on every stream (§2, Oct 17 runs; not re-run). LEC carries that function to
  the routed netlist. SDF gate-level simulation is not part of this gate (G3 as adapted by the caller: LEC chain).

## 4. G4 power (Innovus 25.11, TT 0.80 V 25 °C, on the restored routed DB, at the accepted clock)
- One fresh Innovus session per engine (restoreDesign into the new dir; view_tt; post-route extraction; OCV + CPPR) and,
  in it, one activity file at a time: `read_activity_file -reset`, `read_activity_file -format TCF -scope <top>`,
  `report_power` (W, mW), coverage reports, per-instance power, clock-network power. Template: an earlier project power script.
  Instance/placement/net fingerprint must be unchanged at exit; nothing is saved.
- **Coverage, stated explicitly:** routed flip-flops whose output nets come from the activity file; primary inputs;
  sequential outputs; routed signal nets from the file / propagated / default / set_switching_activity; the power share of
  instances whose outputs are propagated; the power share of post-route-inserted cells (CTS, optimisation/hold buffers,
  tie cells; no RTL/synthesis counterpart). **Acceptance:** 0 default nets on signal logic; flip-flops ≥ 99 % annotated.
- Points: D32 — P1 (gate point), P4s, P4m; D64 — P3, P2; D128 — X64 when routed; PIMI — P4.
- **Energy per detection** E = P × C / f, C = cycles per detection of the cycle-exact command-replay model over all B
  detections of the draw (P1 67,167.0; P4s 1,238.60; P4m 871.81; P3 2,548.34; P2 21,753.7; X64 34,817.9; PIMI 152,809 per
  instance, compile-time 32 trials × 64 steps), with the fresh-draw counts (241–245) beside it.
- **Configurations reported:** (a) the matched-BER point of framing §5 (decided in §6: x16 at 31.02 dB, P4; D32 one stage
  R 4 = BER-matched to PIMI HW, and D32 MDI Ns 8); (b) the G3/G4 gate point P1 on D32; (c) q32 (P3) and P2 on D64,
  Antiphase only.
- Also: det/s = f / C (one engine); det/s/mm² over the post-route **die** area (`area_public.txt`) and over core area;
  pJ per decision = E / (D × D-ops per detection) (one spin decision per lane per D-op; PIMI: 64 spins × 32 trials × 64
  steps = 131,072 per instance); pJ per lane-update (D × R-ops per detection).
- Power-group split (sequential / combinational / clock / macro / leakage) from the report; no new function-group rules.

## 5. G2 timing extra: slow-corner clock (analysis only; Innovus STA on the restored DB)
- Slow view: SSG 0.72 V 125 °C std cells + the SSG macro views (`macros_gen/views_ssg_*`, present for every macro of D32,
  D64, D128) + the kit's RCmax extraction at 125 °C, built by evaluating the server MMMC (`flow/pnr/mmmc.tcl`) with
  PNR_CORNER = SSG and renamed objects (no kit path in project scripts).
- Constraints: the engine's own routed SDC (D32 `sdc/ape_d32_p1150.sdc`, D64 `v14_d64_p1000/out/final.sdc`) rescaled by
  `sdc_scale.py` (md5 ce77aa59…) to candidate periods in 50 ps steps (period, 5 % setup uncertainty, 25 % I/O). Propagated
  clock. The I/O source latency is re-derived for each slow view by `update_io_latency -source` (the same contract the TT
  closure used: ccopt's I/O latency update, eight consistent min/max early/late values in the saved latency file).
- **Control first:** in the same session, the accepted view_tt is timed as saved, and the same procedure (new mode + view at
  the accepted period, TT corner, update_io_latency) must reproduce the accepted TT WNS within ±5 ps; otherwise the method
  is diagnosed before any SS number is used.
- Walk: start at the predicted SS period; if setup WNS (all path groups) ≥ 0, step down 50 ps until it fails; else step up
  50 ps until it passes (≤ 12 steps; slack is monotone in the period). **SS clock = the shortest passing period.** Also
  reported: the internal-only clock (reg2reg + reg2cgate groups) and SS hold at the SS clock.
- **Fast-corner hold cannot be checked:** no FF macro views exist (only TT and SSG). Stated as a limitation; no macro views
  are generated without asking the caller.

## 6. G5 fairness (from the RTL and the released files; no simulation)
For Antiphase and PIMI: number format, MACs or adder/comparator lanes per lane, whether the coupling product uses the
repeated-block (Kronecker, 1·1ᵀ ⊗ G) form, problem size supported, matched-BER operating point.
**Problem-size finding (read from the released RTL before freezing):** PIMI's released HLS kernel is a 64-spin design
(J in 64 banks of 64 × 16-bit words = 64 × 64; 64 start-spin words; 32 trials and 64 steps compile-time). q32 in the DI
formulation PIMI's BER was measured with (`mimo.ising_delta_at`, K = 1: 2K = 2 spins per real dimension, D = 64) needs 128
spins, so **the released RTL does not fit q32**; the matched-BER point for the PIMI row is **x16 at 31.02 dB (P4)**, where
PIMI HW is 6.2e-4 (milestone-D algorithm; the released RTL's own noise table gives 4.74e-3) and Antiphase one stage R 4 is
8.1e-4 (Ns 8 multi-stage: 0 errors). The framing's "128 spins at K = 2" is 128 spins at K = 1 (P = 2K = 2 copies).

## 7. Resources and guards
hostC: CPUs 104–111 only (≤ 8; the D128 Innovus run is on 96–103), hostD: CPUs 104–111 only (PIMI on 96–103).
guard.py (flow v2, md5 76dd94c2…) RSS cap and timeout per job (power ≥ 12 h; LEC 6 h; STA 12 h), taskset, bwrap with a
read-only root, <SCRATCH> writable, accepted run dirs read-only, TMPDIR/XDG in the gate dir. Nothing under
<HOME>. Other users' processes are never touched. Failed attempts are renamed `*_failN` and logged in `RUNLOG.txt`.
There is no LEDGER in `A/` on hostC; the dated record is the gate dir's `RUNLOG.txt` (and a short `LEDGER.md` created
in the gate dir at the end).

## 8. Prediction (frozen 22:26 UTC, before any result of this work)
Basis: the Oct 17 post-route TCF powers of the same v1.4 netlists on the old flow at TT 1.0 ns (D32: P1 84.2, P4s 75.2,
P4m 76.6 mW, leakage 0.22, clock tree 4.5–4.9 mW, nets 76–80 % from file; D64: P2 178.9, P3 173.0 mW, leakage 0.43).
Energy per cycle is the invariant. Flow v2 r4 changes: four-supply mesh and taps (no cell power), post-route setup+hold
optimisation; D32 std-cell area −5 % (60,470 vs 63,825 µm², relaxed 1.15 ns) → energy per cycle −3 %; D64 +1.8 % → +1 %.
| Quantity | Prediction | Range |
|---|---|---|
| LEC RTL ≡ fv_map ≡ syn ≡ routed, D32 and D64 | all Equivalent; 0 non-eq, 0 aborted | (risk: aborts on the multipliers in the fv_map stage) |
| Flip-flops annotated from the file (routed) | ≥ 99.5 % | 99–100 % |
| Routed signal nets from the file | 80 % | 70–92 % |
| Default nets | 0 | — |
| Power share in propagated logic | 10 % | 4–20 % |
| Power share in post-route-inserted cells | 8 % | 3–15 % |
| Clock network share of power | 6 % | 4–12 % |
| **D32 P1 power (1.15 ns)** | **71.1 mW** | 64–78 |
| D32 P4s / P4m power (1.15 ns) | 63.5 / 64.6 mW | 57–70 / 58–71 |
| D32 leakage | 0.21 mW | 0.15–0.30 |
| **D64 P3 / P2 power (1.00 ns)** | **174.7 / 180.7 mW** | 159–190 / 164–197 |
| D64 leakage | 0.43 mW | 0.3–0.6 |
| **Energy per detection D32 P1** | **5.49 µJ** | 4.98–6.00 |
| Energy per detection D32 P4s / P4m (matched-BER point) | **90.4 / 64.8 nJ** | 82–99 / 59–71 |
| Energy per detection D64 P3 / P2 | **0.445 / 3.93 µJ** | 0.405–0.485 / 3.57–4.29 |
| pJ per decision D32 P1 / P4s / D64 P3 | 2.69 / 2.76 / 3.40 | ±10 % |
| D128 X64 (1.05 ns): power, E/det | 381 mW, 13.9 µJ | 320–450 mW, 11.7–16.5 µJ |
| PIMI P4 (1.0 ns): power, E/det | 327 mW, 50 µJ | 280–400 mW, 43–61 µJ |
| SS clock (all groups), D32 / D64 | **1.80 / 1.60 ns** | 1.65–1.95 / 1.45–1.75 |
| TT control reproduces the accepted WNS | yes (±5 ps) | — |
Against the chair's 8.5 µJ prediction for Antiphase P1 (G6), this predicts **5.5 µJ: lower by 1.5×**, inside the 3× band.
The outcome is printed whichever way it falls.
