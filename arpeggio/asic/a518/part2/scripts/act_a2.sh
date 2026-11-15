#!/bin/bash
# A5.18 check (gate1.txt): ENGINE_ARPEGGIO_BAL activity of the copy chord/rtl_a2 on stim_x64arpeggio; p1 rtl_out must equal act/x64arpeggio/p1 byte for byte.
R=<SCRATCH>/arpeggio_asic_20261017; P=$R/a518/part2
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
taskset -c 14-15 nice -n 10 bash $P/scripts/act_run_a518.sh x64arpeggio_a2 $R/chord/rtl_a2/arpeggio_engine.sv <SCRATCH>/arpeggio_ber_20261024/a518_rtl/runs/stim_x64arpeggio 128 4 +define+ENGINE_ARPEGGIO_BAL
if cmp -s $P/act/x64arpeggio_a2/p1/rtl_out.txt $P/act/x64arpeggio/p1/rtl_out.txt; then r=IDENTICAL; else r=DIFFERS; fi
echo "$(date -u +%FT%TZ) balanced-start check: x64arpeggio_a2 p1 rtl_out $r to x64arpeggio p1 ($(sha256sum $P/act/x64arpeggio_a2/p1/rtl_out.txt | cut -c1-12) vs $(sha256sum $P/act/x64arpeggio/p1/rtl_out.txt | cut -c1-12))" >> $R/a518/RUNLOG.txt
echo $r > $P/act/x64arpeggio_a2/gate1.txt
