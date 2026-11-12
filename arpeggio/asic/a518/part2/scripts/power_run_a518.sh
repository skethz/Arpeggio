#!/bin/bash
# A5.18 part 2 W3 (PROTOCOL_A518_part2.md 0d0eeeee): copy of fa_a511/power_run.sh with the TCF source, DB and output as arguments.
# usage: power_run_a518.sh <key> <tag> <tcf at 1000 ps> <routed db .enc.dat> <top> <period ps> <cpu list>
set -u
R=<SCRATCH>/antiphase_asic_20261017; G=$R/fa_a511/gate_scripts; P=$R/a518/part2
key=$1; t=$2; T0=$3; DB=$4; TOP=$5; PS=$6; C=$7
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
K=$(python3 -c "print($PS / 1000.0)"); T1=$P/power/tcf/${key}_${t}_p$PS.tcf
python3 $G/tcf_rescale.py $T0 $T1 $K > $T1.rescale.log 2>&1 || { echo "$(date -u +%FT%TZ) $key rescale FAILED" >> $R/a518/RUNLOG.txt; exit 1; }
W=$P/power/${key}_${t}_p$PS; mkdir -p $W/tmp $W/var_tmp
echo "$(date -u +%FT%TZ) start power $key $t p$PS db $DB tcf $(sha256sum $T0 | cut -c1-12) cpus $C" >> $R/a518/RUNLOG.txt
env PP_CPUS=4 PP_OUT=$W PP_DB=$DB PP_TOP=$TOP "PP_TCFS=$t=$T1" TMPDIR=$W/tmp \
  python3 $R/flow_v2_20261024/guard.py $W 14400 64 -- taskset -c $C bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
  --bind <SCRATCH> <SCRATCH> --bind $W/tmp /tmp --bind $W/var_tmp /var/tmp --chdir $W nice -n 10 \
  <TOOL_LAUNCHER> innovus -no_gui -batch -files $G/power_gate.tcl -log $W/tool
echo "$(date -u +%FT%TZ) end power $key $t p$PS $(grep -h 'Total Power:' $W/$t/power_tt.rpt 2>/dev/null | head -1 | tr -s ' ') $(cat $W/guard_public.json 2>/dev/null)" >> $R/a518/RUNLOG.txt
