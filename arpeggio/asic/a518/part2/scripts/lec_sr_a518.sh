#!/bin/bash
# A5.18 part 2 W4: synthesis netlist -> routed netlist LEC (step 1 of fa_a511/lec_run.sh, project dofile lec_syn_routed.do)
# for a layout changed by the closure pass; RTL -> fv_map -> synthesis is unchanged from gate_r4 / A5.11 (same synthesis DB).
# usage: lec_sr_a518.sh <name> <syn dir> <routed netlist> <top> <cpu list> <threads>
set -u
R=<SCRATCH>/antiphase_asic_20261017; F=$R/flow_v2_20261024; GS=$R/a518/part2/gate_scripts
n=$1; SD=$2; RN=$3; TOP=$4; C=$5; TH=$6
LOG=$R/a518/RUNLOG.txt; [ "$(hostname -s)" = hostC ] && LOG=$R/a518/RUNLOG_hostc.txt
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
L=$R/a518/part2/lec/$n; W2=$L/syn_routed; mkdir -p $W2/run $L/tmp $L/var_tmp
awk '/^add_search_path \. /{f=1} f{print} f&&/^read_library/{r=1} r&&!/\\$/{exit}' $SD/fv/$TOP/rtl_to_fv_map.do > $W2/libs_private.do
grep '^add_notranslate_modules' $SD/fv/$TOP/rtl_to_fv_map.do >> $W2/libs_private.do
sha256sum $SD/out/netlist.v $RN $GS/lec_syn_routed.do > $L/INPUTS.sha256
echo "$(date -u +%FT%TZ) start lec syn_routed $n cpus $C" >> $LOG
env L_WORK=$W2 L_THREADS=$TH L_GOLDEN=$SD/out/netlist.v L_REVISED=$RN L_TOP=$TOP TMPDIR=$L/tmp \
  python3 $F/guard.py $W2/run 14400 32 -- taskset -c $C bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
  --bind <SCRATCH> <SCRATCH> --bind $L/tmp /tmp --bind $L/var_tmp /var/tmp --chdir $W2/run nice -n 10 \
  <TOOL_LAUNCHER> lec -XL -nogui -tclmode -dofile $GS/lec_syn_routed.do
echo "$(date -u +%FT%TZ) end lec syn_routed $n $(cat $W2/run/guard_public.json 2>/dev/null) $(grep -h 'LEC_COUNTS\|Equivalent\|Non-equivalent' $W2/run/*.log 2>/dev/null | tail -3 | tr -s ' ' | paste -sd'|')" >> $LOG
