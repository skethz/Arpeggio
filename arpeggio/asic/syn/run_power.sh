#!/bin/bash
# usage: run_power.sh <opt.db> <saif> <scope> <scale> <out prefix>
R=<SCRATCH>/antiphase_asic_20261017
export TMPDIR=$R/tmp PW_DB=$1 PW_SAIF=$2 PW_SCOPE=$3 PW_SCALE=$4 PW_OUT=$5
nice -n 5 <TOOL_LAUNCHER> genus -no_gui -batch -files $R/flow/power_saif.tcl -log ${5}_genus > ${5}.stdout 2>&1
echo "exit $?" >> ${5}.stdout
