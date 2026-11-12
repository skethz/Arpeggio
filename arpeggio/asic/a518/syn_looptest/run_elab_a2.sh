#!/bin/bash
# A5.18 A2: elaboration-only test of ape/rtl_a2/ape_engine_fa.sv with APE_FA_BAL, the production syn_generic.tcl (no loop-limit override).
R=<SCRATCH>/antiphase_asic_20261017; T=$R/a518/syn_looptest; F=$R/flow_v2_20261024
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache TMPDIR=$R/tmp
export SYN_TOP=ape_engine SYN_FILES="$R/ape/rtl_srv/ape_mem_gf22.sv $R/ape/rtl_a2/ape_engine_fa.sv" SYN_DEFINES="APE_FA_BAL" SYN_EFFORT=medium SYN_PARAMS="D=128 A=4 SEEDL=4" SYN_MACROS="$(cat $F/macros_ape_d128.txt)"
export SYN_OUT=$T/run_a2 SYN_PERIOD=1000 SYN_CPUS=2 SYN_STOP=elab
cd $T/run_a2 && /usr/bin/time -v nice -n 10 taskset -c 12-13 <TOOL_LAUNCHER> genus -no_gui -batch -files $R/flow/syn_generic.tcl -log $T/run_a2/genus_elab > $T/run_a2/stdout.log 2> $T/run_a2/time.log
echo "exit $?" >> $T/run_a2/time.log
