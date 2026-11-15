#!/bin/bash
# A5.11 synthesis of the first-accept engine, same settings as v14
export HOME=<SCRATCH>/arpeggio_asic_20261017/home XDG_CONFIG_HOME=<SCRATCH>/arpeggio_asic_20261017/home/.config XDG_CACHE_HOME=<SCRATCH>/arpeggio_asic_20261017/home/.cache
export SYN_TOP=chord_engine SYN_FILES="<SCRATCH>/arpeggio_asic_20261017/chord/rtl_srv/engine_mem_gf22.sv <SCRATCH>/arpeggio_asic_20261017/chord/rtl/arpeggio_engine.sv" SYN_DEFINES="" SYN_EFFORT=medium
d=$1; sl=$2
export SYN_PARAMS="D=$d A=4 SEEDL=$sl" SYN_MACROS="$(cat <SCRATCH>/arpeggio_asic_20261017/flow_v2_20261024/macros_chord_d$d.txt)"
echo "$(date -u +%FT%TZ) start syn arpeggio_d${d}_p1000" >> <SCRATCH>/arpeggio_asic_20261017/arpeggio_a511/RUNLOG.txt
nice -n 5 <SCRATCH>/arpeggio_asic_20261017/flow/run_syn.sh <SCRATCH>/arpeggio_asic_20261017/arpeggio_a511/syn/arpeggio_d${d}_p1000 1000 6
echo "$(date -u +%FT%TZ) end syn arpeggio_d${d}_p1000 $(tail -1 <SCRATCH>/arpeggio_asic_20261017/arpeggio_a511/syn/arpeggio_d${d}_p1000/time.log)" >> <SCRATCH>/arpeggio_asic_20261017/arpeggio_a511/RUNLOG.txt
