#!/bin/bash
# usage: SYN_TOP=.. SYN_FILES=".." [SYN_DEFINES SYN_PARAMS SYN_MACROS SYN_RETIME SYN_EFFORT] run_syn.sh <out dir> <period ps> <cpus>
R=<SCRATCH>/antiphase_asic_20261017
export TMPDIR=$R/tmp SYN_OUT=$1 SYN_PERIOD=$2 SYN_CPUS=$3
mkdir -p $1 && cd $1
/usr/bin/time -v nice -n 5 <TOOL_LAUNCHER> genus -no_gui -batch -files $R/flow/syn_generic.tcl -log $1/genus > $1/stdout.log 2> $1/time.log
echo "exit $?" >> $1/time.log
