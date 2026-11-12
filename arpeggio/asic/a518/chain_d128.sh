#!/bin/bash
set -u
R=<SCRATCH>/antiphase_asic_20261017; F=$R/flow_v2_20261024; O=$R/a518
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
log(){ echo "$(date -u +%FT%TZ) $*" >> $O/RUNLOG.txt; }
S=$O/syn/fa_d128_p1000; TOP=ape_engine_D128_A4_SEEDL4; M="$(cat $F/macros_ape_d128.txt)"
export SYN_TOP=ape_engine SYN_FILES="$R/ape/rtl_srv/ape_mem_gf22.sv $R/ape/rtl/ape_engine_fa.sv" SYN_DEFINES="" SYN_EFFORT=medium SYN_PARAMS="D=128 A=4 SEEDL=4" SYN_MACROS="$M"
log "start S128 syn fa_d128_p1000 rtl $(sha256sum $R/ape/rtl/ape_engine_fa.sv | cut -c1-12)"
taskset -c 0-5 nice -n 5 $R/flow/run_syn.sh $S 1000 6
log "end S128 $(tail -1 $S/time.log)"
if ! grep -q '^exit 0' $S/time.log || [ ! -s $S/out/netlist.v ]; then log "S128 SYN_FAILED"; exit 1; fi
python3 $F/sdc_scale.py $S/out/final.sdc $O/sdc/fa_d128_p1200.sdc 1200
python3 $F/sdc_scale.py $S/out/final.sdc $O/sdc/fa_d128_p1250.sdc 1250
log "launch P128a pnr fa_d128_p1200 hostB cpus 0-7"
setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/fa_d128_p1200 $S $TOP "$M" 0.6 8 final 86400 0-7 $O/sdc/fa_d128_p1200.sdc > $O/logs/pnr_fa_d128_p1200.out 2>&1 < /dev/null &
until [ -s $O/closure/fa_d64_p1000_cl/guard_public.json ]; do sleep 120; done
log "launch P128b pnr fa_d128_p1250 hostB cpus 16-23 (after C2 ended)"
setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/fa_d128_p1250 $S $TOP "$M" 0.6 8 final 86400 16-23 $O/sdc/fa_d128_p1250.sdc > $O/logs/pnr_fa_d128_p1250.out 2>&1 < /dev/null &
wait
