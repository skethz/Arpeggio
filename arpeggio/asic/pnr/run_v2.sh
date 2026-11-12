#!/bin/bash
# usage: run_v2.sh <out dir> <syn dir> <top> "<macros>" <util> <cpus> <stop> <timeout_s> <cpu list> [sdc override]
set -u
A=<SCRATCH>/antiphase_asic_20261017; F=$A/flow_v2_20261024
O=$1; S=$2; T=$3; M=$4; U=$5; C=$6; STOP=$7; TMO=$8; CPUL=$9; SDC=${10:-}
mkdir -p $O/tmp $O/var_tmp $O/db $O/reports
ENVS="PNR_OUT=$O PNR_SYN=$S PNR_TOP=$T PNR_MACROS=$M PNR_UTIL=$U PNR_CPUS=$C PNR_CORNER=TT FLOW_STOP=$STOP FLOW_MAPS=$F/maps"
[ -n "$SDC" ] && ENVS="$ENVS PNR_SDC_OVERRIDE=$SDC"
echo "$(date -u +%FT%TZ) start $O stop=$STOP" >> $F/runs.log
env ${FLOW_PGPROBE:+FLOW_PGPROBE=$FLOW_PGPROBE} PNR_OUT=$O PNR_SYN=$S PNR_TOP=$T "PNR_MACROS=$M" PNR_UTIL=$U PNR_CPUS=$C PNR_CORNER=TT FLOW_STOP=$STOP FLOW_MAPS=$F/maps ${SDC:+PNR_SDC_OVERRIDE=$SDC} \
  python3 $F/guard.py $O $TMO 120 -- taskset -c $CPUL bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev --bind <SCRATCH> <SCRATCH> --bind $O/tmp /tmp --bind $O/var_tmp /var/tmp --chdir $O nice -n 5 <TOOL_LAUNCHER> innovus -no_gui -batch -files $F/pnr_v2.tcl -log $O/tool
echo "$(date -u +%FT%TZ) end $O $(cat $O/guard_public.json) $(grep -o 'FLOW_V2_DONE_[A-Z]*' $O/stdout.log | tail -1)" >> $F/runs.log
