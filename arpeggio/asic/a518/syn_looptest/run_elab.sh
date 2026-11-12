#!/bin/bash
R=<SCRATCH>/antiphase_asic_20261017; T=$R/a518/syn_looptest; F=$R/flow_v2_20261024
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache TMPDIR=$R/tmp
export SYN_TOP=ape_engine SYN_FILES="$R/ape/rtl_srv/ape_mem_gf22.sv $R/ape/rtl/ape_engine_fa.sv" SYN_DEFINES="APE_FA_BAL" SYN_EFFORT=medium SYN_PARAMS="D=128 A=4 SEEDL=4" SYN_MACROS="$(cat $F/macros_ape_d128.txt)"
export SYN_OUT=$T/run SYN_PERIOD=1000 SYN_CPUS=4 SYN_STOP=elab SYN_LOOP_LIMIT=$1
cd $T/run && /usr/bin/time -v nice -n 10 taskset -c 8-11 <TOOL_LAUNCHER> genus -no_gui -batch -files $T/syn_generic_loop.tcl -log $T/run/genus_$1 > $T/run/stdout_$1.log 2> $T/run/time_$1.log
echo "exit $?" >> $T/run/time_$1.log
