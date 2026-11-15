#!/bin/bash
# r2: same as lec_rtl_syn_a518.sh except the guard limit 14400 s -> 43200 s and the output dir rtl_syn_r2 (the RTL -> fv_map compare needs longer: datapath analysis 7,786 s; Chord D128 took 3 h 43 min in gate_r4).
# A5.18: RTL -> fv_map -> synthesis LEC of a synthesis DB; step 2 of arpeggio_a511/lec_run.sh (Genus write_do_lec,
# gate_r4 count-line edit). Step 1 (syn -> routed) runs later by lec_sr_a518.sh on the routed netlist.
# usage: lec_rtl_syn_a518.sh <run name> <syn dir> <top> <cpu list> <threads> <rtl file hashed in INPUTS>
set -u
R=<SCRATCH>/arpeggio_asic_20261017; O=$R/a518; F=$R/flow_v2_20261024; GS=$R/arpeggio_a511/gate_scripts
RUN=$1; S=$2; TOP=$3; C=$4; TH=$5; RTL=$6
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
L=$O/part2/lec/$RUN; W=$L/rtl_syn_r2; mkdir -p $W/genus $L/tmp $L/var_tmp
cp -r $S/fv $W/fv
awk '/^add_search_path \. /{f=1} f{print} f&&/^read_library/{r=1} r&&!/\\$/{exit}' $S/fv/$TOP/rtl_to_fv_map.do > $W/libs_private.do
sha256sum $S/out/netlist.v $S/out/opt.db $RTL > $L/INPUTS_rtl_syn_r2.sha256
run() { # $1 out dir, rest = command
  local out=$1; shift
  echo "$(date -u +%FT%TZ) start lec $(basename $out) $RUN cpus $C" >> $O/RUNLOG.txt
  env TMPDIR=$L/tmp python3 $F/guard.py $out 43200 32 -- taskset -c $C bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
    --bind <SCRATCH> <SCRATCH> --bind $L/tmp /tmp --bind $L/var_tmp /var/tmp --chdir $out nice -n 10 "$@"
  echo "$(date -u +%FT%TZ) end lec $(basename $out) $RUN $(cat $out/guard_public.json 2>/dev/null)" >> $O/RUNLOG.txt
}
# 2. Genus writes the composite RTL -> fv_map -> netlist dofile from the synthesis DB (read_db only)
env L_DB=$S/out/opt.db L_NETLIST=$S/out/netlist.v L_WORK=$W \
  bash -c "$(declare -f run); $(declare -p R O F L C RUN); run $W/genus <TOOL_LAUNCHER> genus -no_gui -batch -files $GS/genus_write_lec.tcl -log $W/genus/genus"
# same edit as gate_r4: the fv_map->netlist count line right after the first report_statistics (gate_r4: 146a147)
awk '{print} /^report_statistics/ && !d {print "puts \"LEC_COUNTS_FVMAP_NETLIST compare [get_compare_points -count] equivalent [get_compare_points -equivalent -count] noneq [get_compare_points -NONequivalent -count] abort [get_compare_points -abort -count] unknown [get_compare_points -unknown -count]\""; d=1}' $W/lec_genus.do > $W/lec.do
[ -s $W/lec.do ] && [ $(($(wc -l < $W/lec.do) - $(wc -l < $W/lec_genus.do))) = 1 ] || { echo "$(date -u +%FT%TZ) LEC_PREP_R2_FAILED $RUN" >> $O/RUNLOG.txt; exit 1; }
run $W <TOOL_LAUNCHER> lec -XL -nogui -tclmode -dofile $W/lec.do
echo "$(date -u +%FT%TZ) LEC_RTL_SYN_R2_DONE $RUN" >> $O/RUNLOG.txt
