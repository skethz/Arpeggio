#!/bin/bash
# usage: run_closure.sh <flow dir> <out dir> <db .enc.dat> <top> <timeout_s> <cpu list> [report setup views]
set -u
F=$1; O=$2; DB=$3; TOP=$4; TMO=$5; CPUL=$6; VIEWS=${7:-}
mkdir -p $O/tmp $O/var_tmp
echo "$(date -u +%FT%TZ) start closure $O from $DB" >> $F/runs.log
env PNR_OUT=$O CL_DB=$DB CL_TOP=$TOP FLOW_MAPS=$F/maps ${VIEWS:+FLOW_REPORT_SETUP_VIEWS=$VIEWS} \
  python3 $F/guard.py $O $TMO 96 -- taskset -c $CPUL bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev --bind <SCRATCH> <SCRATCH> --bind $O/tmp /tmp --bind $O/var_tmp /var/tmp --chdir $O nice -n 5 <TOOL_LAUNCHER> innovus -no_gui -batch -files $F/closure_pass.tcl -log $O/tool
echo "$(date -u +%FT%TZ) end closure $O $(cat $O/guard_public.json) $(grep -o 'FLOW_V2_DONE_[A-Z]*' $O/stdout.log | tail -1)" >> $F/runs.log
