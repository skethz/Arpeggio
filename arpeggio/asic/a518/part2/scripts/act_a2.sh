#!/bin/bash
# A5.18 A2 gate (1): APE_FA_BAL activity of the copy ape/rtl_a2 on stim_x64fa; p1 rtl_out must equal act/x64fa/p1 byte for byte.
R=<SCRATCH>/antiphase_asic_20261017; P=$R/a518/part2
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
taskset -c 14-15 nice -n 10 bash $P/scripts/act_run_a518.sh x64fa_a2 $R/ape/rtl_a2/ape_engine_fa.sv <SCRATCH>/ap_ber_20261024/a518_rtl/runs/stim_x64fa 128 4 +define+APE_FA_BAL
if cmp -s $P/act/x64fa_a2/p1/rtl_out.txt $P/act/x64fa/p1/rtl_out.txt; then r=IDENTICAL; else r=DIFFERS; fi
echo "$(date -u +%FT%TZ) A2 gate 1: x64fa_a2 p1 rtl_out $r to x64fa p1 ($(sha256sum $P/act/x64fa_a2/p1/rtl_out.txt | cut -c1-12) vs $(sha256sum $P/act/x64fa/p1/rtl_out.txt | cut -c1-12))" >> $R/a518/RUNLOG.txt
echo $r > $P/act/x64fa_a2/gate1.txt
