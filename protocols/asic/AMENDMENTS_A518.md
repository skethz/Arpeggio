# A5.18 amendments

## A1 (11 Nov 2026, about 04:25Z; frozen before any D = 128 result)
**Finding.** The 64-user Arpeggio pick (A5.8: `abl_far_64_0.1_0.1_0_bal_8`) uses balanced starts, so its RTL needs the `APE_FA_BAL` seeder. That seeder is a per-lane multiply-and-shift plus a pattern table (`ape_engine_fa.sv` line 346).

S128 (part 1 §3) builds the production build without that define, as A5.11 did, where both picks use random starts. That netlist therefore lacks hardware the 64-user operating point needs.

**Added runs**, chained on hostB after N1 ends, on CPUs 8–15 (the 24-thread cap holds):
- **S128bal:** synthesis of D = 128 Arpeggio with `SYN_DEFINES="APE_FA_BAL"`; everything else as S128.
- **P128bal:** P&R of S128bal at 1.20 ns, flow and acceptance as part 1 §3.

**Use in the pairs (§4):**
- The D = 128 Arpeggio entry is P128bal if it is accepted.
- Otherwise it is the accepted random-start build, with the note "balanced-start seeder not costed".
- P128a and P128b run as frozen and are reported either way.

**Sign-off (§5):** the same checks apply to P128bal.

**Unchanged:** the D = 32 and D = 64 picks use random starts, as A5.11 established, so their production builds stand.

## A2 (11 Nov 2026, about 08:30Z; frozen before S128bal is re-run and before any P128bal result)
**Finding.** S128bal failed elaboration: Genus CDFG-457 at `ape_engine_fa.sv` line 89, where `bal_pat` loops to `1 << int'(P)` with a runtime P. With `hdl_max_loop_limit` 65536, elaboration ran 1 h 40 min (34 GB) without finishing and was stopped.

**Also found.** On `stim_x64fa`, the random-start build takes 702,456 cycles, against 291,594 for the `APE_FA_BAL` build. Without balanced starts the engine runs I-ops, so the random-start build's activity is a different workload from the 64-user operating point.

**Change (synthesis compatibility only).** A copy `ape/rtl_a2/ape_engine_fa.sv` (8ef9d1f93f72) bounds the loop at the constant `1 << PMAX` (64) and keeps `v < 2^P` as a guard inside it. Nothing outside `bal_pat` changes (diff: lines 89–90).
- For P ≤ PMAX = 6, the function returns the same pattern for every (P, i). This was checked exhaustively in a Python model; it differs only at P = 7, which the engine never uses (P ∈ {2, 4, 6}).
- The production file `ape/rtl/ape_engine_fa.sv` (ada3059e94fd) is not touched, so S128, P128a/b and every activity run stand.

**Gate.** P128bal starts only if both hold:
1. RTL simulation of the copy with `APE_FA_BAL` on `stim_x64fa` (act tag `x64fa_a2`, the part 2 W2 procedure) gives a `p1/rtl_out.txt` byte-identical to `act/x64fa/p1/rtl_out.txt`.
2. Synthesis exits 0 with a netlist.

If (1) fails, the copy is discarded and A1's random-start fallback stands.

**Runs.**
- **S128bal:** `syn/fa_d128bal_a2_p1000` with SYN_DEFINES "APE_FA_BAL" and the copy in SYN_FILES; everything else as S128 (medium effort, D=128 A=4 SEEDL=4, same macros). hostB CPUs 12–15, 4 threads; the 24-CPU cap holds.
- **P128bal:** `pnr/fa_d128bal_a2_p1200` at 1.20 ns, flow and acceptance as part 1 §3. CPUs 8–15, once the x64fa_rsb chain has ended.

**Use (A1 unchanged).**
- If P128bal is accepted, it is the D = 128 Arpeggio entry, and its activity is `x64fa_a2`: W2's `APE_FA_BAL` build on the same stim.txt.
- Otherwise the entry stays the accepted random-start build, with the note "balanced-start seeder not costed".
- P128a/b and `x64fa_rsb` are reported either way.
- Sign-off (§5) applies to P128bal, with LEC against the copy.

**User decision:** 11 Nov 2026, "Yes, fix RTL" (after "Use P128a/b" the same morning).

## A3 (11 Nov 2026, about 17:35Z; frozen before any 1.30 ns result and before P128bal's result)
**Finding.** No random-start D = 128 layout was accepted:
- P128a (1.20 ns): TT reg2reg setup WNS −14 ps.
- P128b (1.25 ns): setup −139 ps, hold −9 ps.

DRC, connectivity and FINAL passed for both. Part 1 §4 says "both engines walk on in 50 ps steps" if no layout is accepted. A1 and A2 do not say which Arpeggio build walks on.

**Rule.**
- The walk-on uses the balanced build (A2: S128bal from `ape/rtl_a2`), because its activity is the 64-user operating point's.
- The random-start build does not walk on. P128a/b are reported as they are.

**Pre-launch (user "Yes, pre-launch", before P128bal's result).** Two runs, with the flow, utilisation 0.60, 8 CPUs, stop `final` and acceptance of part 1 §3; no closure pass:
- **P130bal:** `a518/pnr/fa_d128bal_a2_p1300`, S128bal at 1.30 ns, hostB CPUs 0–7.
- **C130 (Chord):** `a518/pnr/ape_d128_p1300` on hostC, from Table IV's synthesis `ape/syn/v14_d128_p1000` at 1.30 ns, 8 CPUs that mpstat shows idle at launch.

**Use (part 1 §4 otherwise unchanged).**
- If P128bal is accepted, the D = 128 primary pair is 1.20 ns (Chord `ape_d128_p1200_r4`). The 1.30 ns pair is then "also reported" if both are accepted.
- If P128bal is not accepted, the primary pair is 1.30 ns when P130bal and C130 are both accepted.
- Otherwise both engines walk on in 50 ps steps (balanced build, new Chord run each step) until the stop rule (15 Nov 12:00 CET).

## A4 (13 Nov 2026, 08:15 CET): walk-on stopped by the user before the stop rule; no D = 128 pair
**Finding.** The A3 walk-on ran 1.30–1.70 ns (nine clocks; RUNLOG.txt on hostB, RUNLOG_hostc.txt on hostC):
- Arpeggio (balanced build) accepted at 1.30, 1.35 and 1.55 ns; not at 1.40, 1.45, 1.50, 1.60, 1.65, 1.70.
- Chord (`v14_d128_p1000`, new run per step) accepted at none of the nine.
- No clock has both accepted, so D = 128 has no primary pair.
- Misses: single-path setup slacks of −0.7 to −21 ps and pin-area DRC (SPACING/SHORT on layer IA between `in_data` nets at the left pin strip), which hit every Arpeggio run at 1.60 ns and above.
- The 1.75/1.80/1.85 ns runs (launched 07:18 CET) were stopped after about one hour, before any result. Their directories are kept and not judged.

**User decision (13 Nov 2026, 08:1x CET):** "<instruction>" (stop now and apply part 2 §7), chosen over walking on to the 15 Nov 12:00 stop rule.

**Use.**
- Table IV gets the D = 32 and D = 64 Arpeggio results only (part 2 §7, third bullet). Arpeggio D = 128 has accepted layouts at its own clocks, but none pairs with Chord.
- Part 1 §4 "also reported" stays as data: Arpeggio D = 128 at its shortest accepted period 1.30 ns (`fa_d128bal_a2_p1300`), Chord at 1.20 ns (`ape_d128_p1200_r4`); P128a/b as they are.
- No D = 128 sign-off (part 1 §5) or power (part 2 W3 Q3/Q4/Q7) is run.
- main.tex does not depend on a D = 128 pair: its routed equal-clock comparison is the D = 32/64 1.00 ns pairs (V-B), so nothing in the text changes.

## A5 (13 Nov 2026, about 08:23 CET; frozen before the closure run started at 08:25)
**Finding.** P128bal (`pnr/fa_d128bal_a2_p1200`, Arpeggio balanced build at 1.20 ns) missed acceptance by a single I/O path: TT setup default-group WNS −2 ps (1 path); reg2reg +6 ps, reg2cgate +7 ps; hold 0 ps; DRC 0; connectivity 0; FINAL. Chord's D = 128 layout of Table IV (`ape_d128_p1200_r4`) is accepted at 1.20 ns. Part 1 used one closure pass for exactly this case at D = 32 (C1, Chord) and D = 64 (C2, Arpeggio): "the same single closure pass to each engine's only near miss under 10 ps"; A3 excluded it for the walk-on only. A4 left D = 128 without a pair.

**User decision (13 Nov 2026):** "<instruction>", after being shown this option, the 1.30 ns own-clock reading and the 1.30 ns Chord closure fallback.

**Run.**
- **P128bal_cl:** one closure pass, `flow_v2_20261024/run_closure.sh` (closure_pass 04c5a777…, as C1/C2), on `pnr/fa_d128bal_a2_p1200/db/final.enc.dat`, top `ape_engine_D128_A4_SEEDL4`, output `closure/fa_d128bal_a2_p1200_cl`, 8 hostB CPUs, guard 21600 s. Acceptance as part 1 §3. No second pass.
- Started alongside, since they do not depend on the closure result: the x64fa_a2 TCF (part 2 W2: Genus on S128bal's `opt.db`, SAIF `act/x64fa_a2/p2/act_x64fa_a2.saif`, as `chain_x64rsb.sh`), and the RTL → fv_map → synthesis LEC of S128bal (A5.11 `lec_run.sh` step 2, RTL = `ape/rtl_a2` copy).

**Use.**
- If P128bal_cl is accepted, the D = 128 primary pair is **1.20 ns**: Arpeggio P128bal "with one closure pass" and Chord `ape_d128_p1200_r4`. Part 2 then applies as frozen: W3 Q3 (x64fa_a2 TCF rescaled to 1200 ps on P128bal_cl), Q4 = the existing Chord x64ap 206.38892 mW; W4 sign-off for P128bal_cl (LEC syn → routed after the RTL side, SS setup by `sta_ss_v3.tcl` with accept 1200, area); Q7 on the other accepted Arpeggio D = 128 layouts (P130bal, P135bal, P155bal) as "also reported"; §4 formulas with x̂_64 = x_F 0.558199 × c_64 (W1, RUNLOG 04:29Z); §5 decision terms.
- If it is not accepted, D = 128 stays without a pair (A4). The next options (one closure pass on C130, −6 ps at 1.30 ns; or each engine at its own shortest clock) are the user's call.
- Paper text changes stay the user's call (part 2 §7, previews only).

**A5 fail branch (user, 13 Nov 2026, about 08:28 CET, before the closure result): "<instruction>"** (if not accepted, run both). If P128bal_cl is not accepted, both of the following run without a further ask:
- **C130_cl:** one closure pass (`run_closure.sh`, as C1/C2) on `pnr/ape_d128_p1300` (Chord at 1.30 ns, reg2reg −6 ps on one path, DRC 0) on hostC, output `closure/ape_d128_p1300_cl`. If accepted, the D = 128 primary pair is **1.30 ns**: Arpeggio P130bal (no closure pass) and Chord C130 "with one closure pass". Part 2 then applies at 1.30 ns: Q3 on P130bal (x64fa_a2, 1300 ps), Q4 on C130_cl (x64ap, 1300 ps), W4 for both, Q7 on P135bal and P155bal.
- **Own clocks (part 1 §4 "also reported"):** Arpeggio P130bal at 1.30 ns vs Chord `ape_d128_p1200_r4` at 1.20 ns: Q3 power on P130bal (x64fa_a2, 1300 ps), Chord's existing x64ap 206.38892 mW; W4 for P130bal; ratios ρ_t = x̂ · 1300/1200 and ρ_E = x̂ · (P_A · 1300)/(P_Ch · 1200), labelled "each at its own shortest accepted clock".
- If C130_cl is accepted, the 1.30 ns pair is primary and the own-clock reading is also reported; if not, the own-clock reading is reported alone and D = 128 has no pair.

## A6 (13 Nov 2026, about 12:33 CET; run procedure only, after the A5 power and ratio results were known)
**Finding.** The RTL → fv_map → synthesis LEC of S128bal (`part2/lec/P128bal_cl/rtl_syn`) was killed by its own 14,400 s guard at 12:27 CET. Its fv_map → synthesis half had finished: 46,778 / 46,778 Equivalent, 0 NEQ, 0 abort, 0 unknown. The RTL → fv_map half was still in `compare` after 7,786 s of datapath analysis, with no NEQ or abort reported. Chord's D = 128 RTL → fv_map took 3 h 43 min in gate_r4. The 14,400 s limit was my own choice when I wrote `lec_rtl_syn_a518.sh`, not a protocol value.

**Change.** Rerun as `rtl_syn_r2` by `lec_rtl_syn_a518_r2.sh`, identical except for two things: the guard is 43,200 s, and output goes to its own directory. Same Genus/LEC dofiles, same inputs (`INPUTS_rtl_syn_r2.sha256`), hostB CPUs 17, 18, 20, 22. This follows the standing rule: failed runs are analysed and rerun (user, 12 Nov).
- A first launch at 12:32 wrote for about 20 s into the first run's `rtl_syn/`, because one path edit had not applied. I stopped it.
  - Overwritten or added: `genus/stdout.log`, `genus.log1`/`genus.cmd1`, and a regenerated `libs_private.do` from the same source.
  - A stray nested copy `fv/fv`, identical to the synthesis `fv`, was removed.
  - The first run's `lec.log`, `lec.do`, `lec_genus.do` and `genus/genus.log` are untouched.

**Use.** W4 for the D = 128 Arpeggio entry is complete when `rtl_syn_r2` reports all compare points Equivalent. Until then, the D = 128 row says "RTL → fv_map pending". A non-equivalent or aborted point is reported as it is.
