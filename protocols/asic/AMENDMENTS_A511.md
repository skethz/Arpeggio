# A5.11 amendments

## A1 (7 Nov 2026, 05:45 CET; before any simulation ran)
PROTOCOL_A511 §4 says both activity passes run at the engine's accepted period. Instead, they run at 1000 ps, which is the synthesis period and the period of the v14 SAIFs. Each TCF is then rescaled in time to its engine's accepted period by changing only the duration token, as RESULTS.md §2 did for the Antiphase D32 TCF (K = 1.15).

The toggle counts and duties are unchanged, so the energy per cycle is unaffected. The reason is speed: the activity runs can start while synthesis and P&R are still running.

## A2 (same time): SAIF window end
TE is set by the cycle count of the production run: the cycle of the testbench's `E` line minus its 5 idle cycles. `tb/run_saif.sh` takes the model's `cycles` instead, but no xorshift first-accept model exists. Antiphase uses the same rule, so both engines have one definition.

## A3 (7 Nov 2026, 07:30 CET; after the P1 primary result was seen)
**Declared after the fact.** This was added after the P1 result was known (ρ_t 0.744, ρ_E 1.021, mixed). It does not change the frozen decision rule, and the P1 verdict stays the one at the accepted periods: FA at 1000 ps, Antiphase at 1150 ps.

**What is added.** An exploratory iso-period run: FA D32 routed at 1150 ps, the same clock as the Antiphase control. Its power uses the same p1fa TCF rescaled with K = 1.15.

**Why.** The FA period is 13% shorter than Antiphase's, so timing-driven upsizing may have bought that clock at an energy cost. Without this run, the energy term cannot be separated from that clock choice.

**How it is reported.** Only as a sensitivity row, labelled exploratory.

**How the run started.** The pre-staged 1150 ps run had been stopped at 06:24Z, because the rule did not reach it. It was relaunched at 06:30Z with the same arguments.
