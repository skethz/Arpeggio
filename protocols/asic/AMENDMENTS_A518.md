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
