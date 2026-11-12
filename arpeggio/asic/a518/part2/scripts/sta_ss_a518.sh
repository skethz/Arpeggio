#!/bin/bash
# A5.18 part 2 W4: slow-corner clock walk (sta_ss_v3.tcl, gate_r4 / Table IV SS column method) of a routed layout.
# usage: sta_ss_a518.sh <name> <db .enc.dat> <top> <base sdc> <accept ps> <start ps> <macros file> <cpu list>
set -u
R=<SCRATCH>/antiphase_asic_20261017; F=$R/flow_v2_20261024; P=$R/a518/part2
n=$1; DB=$2; TOP=$3; SB=$4; AP=$5; SP=$6; MF=$7; C=$8
LOG=$R/a518/RUNLOG.txt; [ "$(hostname -s)" = hostC ] && LOG=$R/a518/RUNLOG_hostc.txt
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
O=$P/sta/$n; mkdir -p $O/tmp $O/var_tmp
sha256sum $SB $MF $P/gate_scripts/sta_ss_v3.tcl $R/flow/pnr/mmmc.tcl > $O/INPUTS.sha256
echo "$(date -u +%FT%TZ) start sta_ss $n accept $AP start $SP cpus $C" >> $LOG
env CL_DB=$DB CL_TOP=$TOP PNR_OUT=$O STA_SDC_BASE=$SB STA_ACCEPT_PS=$AP STA_START_PS=$SP STA_FLOW=$F STA_MACROS=$MF STA_CPUS=2 \
  STA_MMMC=$R/flow/pnr/mmmc.tcl TMPDIR=$O/tmp \
  python3 $F/guard.py $O 14400 32 -- taskset -c $C bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
  --bind <SCRATCH> <SCRATCH> --bind $O/tmp /tmp --bind $O/var_tmp /var/tmp --chdir $O nice -n 10 \
  <TOOL_LAUNCHER> innovus -no_gui -batch -files $P/gate_scripts/sta_ss_v3.tcl -log $O/tool
echo "$(date -u +%FT%TZ) end sta_ss $n $(cat $O/guard_public.json 2>/dev/null) | $(cat $O/result_public.txt 2>/dev/null | paste -sd'|')" >> $LOG
