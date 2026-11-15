#!/bin/bash
# A5.18: elaboration-only test of chord/rtl_a2/arpeggio_engine.sv with ENGINE_ARPEGGIO_BAL, the production syn_generic.tcl (no loop-limit override).
R=<SCRATCH>/arpeggio_asic_20261017; T=$R/a518/syn_looptest; F=$R/flow_v2_20261024
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache TMPDIR=$R/tmp
export SYN_TOP=chord_engine SYN_FILES="$R/chord/rtl_srv/engine_mem_gf22.sv $R/chord/rtl_a2/arpeggio_engine.sv" SYN_DEFINES="ENGINE_ARPEGGIO_BAL" SYN_EFFORT=medium SYN_PARAMS="D=128 A=4 SEEDL=4" SYN_MACROS="$(cat $F/macros_chord_d128.txt)"
export SYN_OUT=$T/run_a2 SYN_PERIOD=1000 SYN_CPUS=2 SYN_STOP=elab
cd $T/run_a2 && /usr/bin/time -v nice -n 10 taskset -c 12-13 <TOOL_LAUNCHER> genus -no_gui -batch -files $R/flow/syn_generic.tcl -log $T/run_a2/genus_elab > $T/run_a2/stdout.log 2> $T/run_a2/time.log
echo "exit $?" >> $T/run_a2/time.log
