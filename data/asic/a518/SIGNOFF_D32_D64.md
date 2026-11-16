# Sign-off of the 1.00 ns engines: Table IV rows 7 and 8, Section V-B's D = 32 Chord

Innovus 25.11 static timing and Conformal 25.10 LEC on the routed databases, as for Table IV's other rows (`../sta_public.json`, `../lec_public.json`).
Slacks are worst slacks in ps. SS: 0.72 V, 125 °C, worst-case RC; TT otherwise.
Internal paths are register-to-register and clock-gating paths; I/O paths are the default group (from inputs, to outputs).
The SS clock is the shortest period, in 50 ps steps, at which every path group meets setup at SS, with I/O latency rule R1 of `../sta_public.json` (the rule that reproduces each layout's accepted TT slack).
Row 9 (D = 128) is in [RESULTS_D128.md](RESULTS_D128.md).

| | Arpeggio, D = 32 (row 7) | Arpeggio, D = 64 (row 8) | Chord, D = 32 (Section V-B, Table IV note d) |
| --- | --- | --- | --- |
| Routed layout | `arpeggio_d32_p1000` | `arpeggio_d64_p1000`, one closure pass | `chord_d32_r4b`, one closure pass |
| TT clock | 1.00 ns | 1.00 ns | 1.00 ns |
| TT setup / hold | +6 / ≥ 0 | +3 / +28 | +1 / +29 |
| DRC / connectivity violations | 0 / 0 | 0 / 0 | 0 / 0 |
| SS clock | 1.55 ns | 1.55 ns | 1.55 ns |
| SS setup at 1.55 ns, all groups | +47 | +37 | +41 |
| SS hold at 1.55 ns, internal / I/O | +63 / +39 | +46 / −12 | +61 / −2 |
| LEC RTL → fv_map → synthesis → routed | 12,912 / 12,912 / 12,912 points, all equivalent | 1/1 module pair / 24,374 / 24,374 points, all equivalent | 12,789 / 12,784 (Table IV's D = 32 Chord, same synthesis netlist) / 12,784 points, all equivalent |

No step has a non-equivalent, aborted or unknown point. Both D = 64 Arpeggio layouts (1.00 ns with the closure pass; 1.15 ns in A5.11) read one synthesis netlist, whose RTL → fv_map → synthesis check ran with the 1.15 ns layout.
Table IV's SS column gives these clocks as 645 MHz.
