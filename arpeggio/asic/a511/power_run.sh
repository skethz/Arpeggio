#!/bin/bash
# A5.11 §4: rescale a TCF to the accepted period (gate tcf_rescale.py) and run Innovus TT power (gate power_gate.tcl).
# usage: power_run.sh <tag> <routed run dir> <top> <period ps> <cpu list>
set -u
R=<SCRATCH>/antiphase_asic_20261017; O=$R/fa_a511; t=$1; RUN=$2; TOP=$3; P=$4; C=$5
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
K=$(python3 -c "print($P / 1000.0)"); T0=$O/power/tcf/${t}_1000_netlist.tcf; T1=$O/power/tcf/${t}_p$P.tcf
python3 $O/gate_scripts/tcf_rescale.py $T0 $T1 $K > $O/power/tcf/${t}_p$P.rescale.log 2>&1
W=$O/power/${t}_p$P; mkdir -p $W/tmp $W/var_tmp
echo "$(date -u +%FT%TZ) start power $t p$P run $(basename $RUN)" >> $O/RUNLOG.txt
env PP_CPUS=4 PP_OUT=$W PP_DB=$RUN/db/final.enc.dat PP_TOP=$TOP "PP_TCFS=$t=$T1" TMPDIR=$W/tmp \
  python3 $R/flow_v2_20261024/guard.py $W 14400 64 -- taskset -c $C bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
  --bind <SCRATCH> <SCRATCH> --bind $W/tmp /tmp --bind $W/var_tmp /var/tmp --chdir $W nice -n 10 \
  <TOOL_LAUNCHER> innovus -no_gui -batch -files $O/gate_scripts/power_gate.tcl -log $W/tool
echo "$(date -u +%FT%TZ) end power $t p$P $(cat $W/guard_public.json 2>/dev/null)" >> $O/RUNLOG.txt
