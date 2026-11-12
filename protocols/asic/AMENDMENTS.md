# Amendments to PROTOCOL.md (gate_r4_20261024T2220Z)

## A1 (2026-10-24 22:45 UTC, after the first power reports; a clarification, no number changed)
Innovus lists 34 (D32) and 4 (D64) routed nets with default activity. All are `UNCONNECTED*` nets on QN outputs of
flip-flops whose Q output is annotated from the file; every one has fanout 0 (diagnosis `power/diag_d32_default`,
`default_pins_public.txt`: QN<-Q 34). They are not signal logic, so the acceptance "0 default nets on signal logic" holds.
They are reported as such; no activity is assigned to them.

## A2 (2026-10-24 22:58 UTC, before any slow-corner number is used)
The §5 TT control failed (`sta/d32_fail1`): `update_io_latency -source` is refused once clocks are propagated
(TCLCMD-1411), and the interactive fallback did not reproduce the accepted TT slack (all −104 ps vs +2 ps).
Diagnosis (`sta/diag_d32`): a new view built from the routed SDC **with the saved TT latency file** reproduces the accepted
TT result exactly (all/reg2reg/reg2cgate/default +2/+4/+2/+17 ps), with the base SDC or the saved mode SDC alike, and
creating the SS objects does not perturb it; without a latency file the result is −1/−1/+2/+98 ps.
Replacement rule (`scripts/sta_ss_v2.tcl`): three I/O source-latency rules, each walked at 50 ps steps at SS:
- **R2** re-derived: a latency file of ccopt's form whose source latency is −(mean clock arrival at all register clock
  pins, rise and fall) measured in that corner with zero source latency (the TT closure contract: sinks at the ideal edge);
- **R1** the saved TT latency file unchanged; **R0** no source latency (as an earlier project STA script).
**Primary = R2 if, at TT and the accepted period, R2 reproduces the accepted WNS (all groups) within 5 ps; otherwise R1.**
The internal-only clock (reg2reg + reg2cgate, independent of the I/O rule up to SI) and SS hold at the SS clock are
reported for the primary rule. Predictions are unchanged.
