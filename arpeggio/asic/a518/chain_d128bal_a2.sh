#!/bin/bash
# A5.18: S128bal from the copy chord/rtl_a2 (ENGINE_ARPEGGIO_BAL) on hostB CPUs 12-15 (4 threads), then P128bal at 1.20 ns on CPUs 8-15
# once the act_a2.sh check (gate1.txt: x64arpeggio_a2 rtl_out identical) holds and the x64arpeggio_rsb chain has ended.
set -u
R=<SCRATCH>/arpeggio_asic_20261017; F=$R/flow_v2_20261024; O=$R/a518; P=$O/part2
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
log(){ echo "$(date -u +%FT%TZ) $*" >> $O/RUNLOG.txt; }
S=$O/syn/arpeggio_d128bal_a2_p1000; TOP=chord_engine_D128_A4_SEEDL4; M="$(cat $F/macros_chord_d128.txt)"
export SYN_TOP=chord_engine SYN_FILES="$R/chord/rtl_srv/engine_mem_gf22.sv $R/chord/rtl_a2/arpeggio_engine.sv" SYN_DEFINES="ENGINE_ARPEGGIO_BAL" SYN_EFFORT=medium SYN_PARAMS="D=128 A=4 SEEDL=4" SYN_MACROS="$M"
log "start S128bal syn arpeggio_d128bal_a2_p1000 (ENGINE_ARPEGGIO_BAL, rtl_a2 $(sha256sum $R/chord/rtl_a2/arpeggio_engine.sv | cut -c1-12)) hostB cpus 12-15"
taskset -c 12-15 nice -n 5 $R/flow/run_syn.sh $S 1000 4
log "end S128bal $(tail -1 $S/time.log)"
if ! grep -q '^exit 0' $S/time.log || [ ! -s $S/out/netlist.v ]; then log "S128bal SYN_FAILED"; exit 1; fi
until [ -s $P/act/x64arpeggio_a2/gate1.txt ]; do sleep 120; done
if [ "$(cat $P/act/x64arpeggio_a2/gate1.txt)" != IDENTICAL ]; then log "balanced-start check failed: P128bal not launched; the random-start build stands"; exit 1; fi
while pgrep -u <USER> -f chain_x64rsb.sh > /dev/null; do sleep 120; done
python3 $F/sdc_scale.py $S/out/final.sdc $O/sdc/arpeggio_d128bal_a2_p1200.sdc 1200
log "launch P128bal pnr arpeggio_d128bal_a2_p1200 hostB cpus 8-15 (gate 1 IDENTICAL, x64arpeggio_rsb chain ended)"
setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/arpeggio_d128bal_a2_p1200 $S $TOP "$M" 0.6 8 final 86400 8-15 $O/sdc/arpeggio_d128bal_a2_p1200.sdc > $O/logs/pnr_arpeggio_d128bal_a2_p1200.out 2>&1 < /dev/null &
wait
