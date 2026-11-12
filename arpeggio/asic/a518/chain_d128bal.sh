#!/bin/bash
# A5.18 amendment A1: after N1 ends, S128bal (APE_FA_BAL) on CPUs 8-13, then P128bal at 1.20 ns on CPUs 8-15.
set -u
R=<SCRATCH>/antiphase_asic_20261017; F=$R/flow_v2_20261024; O=$R/a518
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
log(){ echo "$(date -u +%FT%TZ) $*" >> $O/RUNLOG.txt; }
until [ -s $O/pnr/ape_d64_p1150/guard_public.json ]; do sleep 120; done
S=$O/syn/fa_d128bal_p1000; TOP=ape_engine_D128_A4_SEEDL4; M="$(cat $F/macros_ape_d128.txt)"
export SYN_TOP=ape_engine SYN_FILES="$R/ape/rtl_srv/ape_mem_gf22.sv $R/ape/rtl/ape_engine_fa.sv" SYN_DEFINES="APE_FA_BAL" SYN_EFFORT=medium SYN_PARAMS="D=128 A=4 SEEDL=4" SYN_MACROS="$M"
log "start S128bal syn fa_d128bal_p1000 (APE_FA_BAL) hostB cpus 8-13 (N1 ended)"
taskset -c 8-13 nice -n 5 $R/flow/run_syn.sh $S 1000 6
log "end S128bal $(tail -1 $S/time.log)"
if ! grep -q '^exit 0' $S/time.log || [ ! -s $S/out/netlist.v ]; then log "S128bal SYN_FAILED"; exit 1; fi
python3 $F/sdc_scale.py $S/out/final.sdc $O/sdc/fa_d128bal_p1200.sdc 1200
log "launch P128bal pnr fa_d128bal_p1200 hostB cpus 8-15"
setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/fa_d128bal_p1200 $S $TOP "$M" 0.6 8 final 86400 8-15 $O/sdc/fa_d128bal_p1200.sdc > $O/logs/pnr_fa_d128bal_p1200.out 2>&1 < /dev/null &
wait
