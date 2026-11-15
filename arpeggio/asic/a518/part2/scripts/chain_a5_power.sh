#!/bin/bash
# A5.18: power of the D128 pair (1.20 ns), then of the other Arpeggio D128 layouts, x64arpeggio_a2 TCF. usage: chain_a5_power.sh <cpu list>
set -u
R=<SCRATCH>/arpeggio_asic_20261017; A=$R/a518; P=$A/part2; C=$1
TOP=chord_engine_D128_A4_SEEDL4; T=$P/tcf/x64arpeggio_a2_netlist.tcf
bash $P/scripts/power_run_a518.sh Q3 x64arpeggio_a2 $T $A/closure/arpeggio_d128bal_a2_p1200_cl/db/final.enc.dat $TOP 1200 $C
for p in 1300 1350 1550; do bash $P/scripts/power_run_a518.sh Q7_p$p x64arpeggio_a2 $T $A/pnr/arpeggio_d128bal_a2_p$p/db/final.enc.dat $TOP $p $C; done
echo "$(date -u +%FT%TZ) A5 power chain done" >> $A/RUNLOG.txt
