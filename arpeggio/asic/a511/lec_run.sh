#!/bin/bash
# A5.11 G3 LEC for one accepted FA run, same chain as gate_r4: Genus write_do_lec (RTL -> fv_map -> syn netlist),
# then project dofile lec_syn_routed.do (syn netlist -> routed). usage: a511_lec.sh <d> <seedl> <run name> <cpu list> <threads>
set -u
R=<SCRATCH>/antiphase_asic_20261017; O=$R/fa_a511; F=$R/flow_v2_20261024; GS=$O/gate_scripts
d=$1; sl=$2; RUN=$3; C=$4; TH=$5
TOP=ape_engine_D${d}_A4_SEEDL${sl}; S=$O/syn/fa_d${d}_p1000; RD=$O/pnr/$RUN
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
L=$O/lec/$RUN; W=$L/rtl_syn; W2=$L/syn_routed; mkdir -p $W/genus $W2 $L/tmp $L/var_tmp
cp -r $S/fv $W/fv
awk '/^add_search_path \. /{f=1} f{print} f&&/^read_library/{r=1} r&&!/\\$/{exit}' $S/fv/$TOP/rtl_to_fv_map.do > $W/libs_private.do
cp $W/libs_private.do $W2/libs_private.do
grep '^add_notranslate_modules' $S/fv/$TOP/rtl_to_fv_map.do >> $W2/libs_private.do
sha256sum $S/out/netlist.v $RD/final_netlist_private.v $R/ape/rtl/ape_engine_fa.sv > $L/INPUTS.sha256
run() { # $1 out dir, rest = command
  local out=$1; shift
  echo "$(date -u +%FT%TZ) start lec $(basename $out) $RUN cpus $C" >> $O/RUNLOG.txt
  env TMPDIR=$L/tmp python3 $F/guard.py $out 14400 32 -- taskset -c $C bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
    --bind <SCRATCH> <SCRATCH> --bind $L/tmp /tmp --bind $L/var_tmp /var/tmp --chdir $out nice -n 10 "$@"
  echo "$(date -u +%FT%TZ) end lec $(basename $out) $RUN $(cat $out/guard_public.json 2>/dev/null)" >> $O/RUNLOG.txt
}
# 1. syn -> routed (independent of step 2; run first, it is short)
mkdir -p $W2/run
env L_WORK=$W2 L_THREADS=$TH L_GOLDEN=$S/out/netlist.v L_REVISED=$RD/final_netlist_private.v L_TOP=$TOP \
  bash -c "$(declare -f run); $(declare -p R O F L C RUN); run $W2/run <TOOL_LAUNCHER> lec -XL -nogui -tclmode -dofile $GS/lec_syn_routed.do"
# 2. Genus writes the composite RTL -> fv_map -> netlist dofile from the synthesis DB (read_db only)
env L_DB=$S/out/opt.db L_NETLIST=$S/out/netlist.v L_WORK=$W \
  bash -c "$(declare -f run); $(declare -p R O F L C RUN); run $W/genus <TOOL_LAUNCHER> genus -no_gui -batch -files $GS/genus_write_lec.tcl -log $W/genus/genus"
# same edit as gate_r4: the fv_map->netlist count line right after the first report_statistics (gate_r4: 146a147)
awk '{print} /^report_statistics/ && !d {print "puts \"LEC_COUNTS_FVMAP_NETLIST compare [get_compare_points -count] equivalent [get_compare_points -equivalent -count] noneq [get_compare_points -NONequivalent -count] abort [get_compare_points -abort -count] unknown [get_compare_points -unknown -count]\""; d=1}' $W/lec_genus.do > $W/lec.do
[ -s $W/lec.do ] && [ $(($(wc -l < $W/lec.do) - $(wc -l < $W/lec_genus.do))) = 1 ] || { echo "$(date -u +%FT%TZ) LEC_PREP_FAILED $RUN" >> $O/RUNLOG.txt; exit 1; }
run $W <TOOL_LAUNCHER> lec -XL -nogui -tclmode -dofile $W/lec.do
echo "$(date -u +%FT%TZ) LEC_CHAIN_DONE $RUN" >> $O/RUNLOG.txt
