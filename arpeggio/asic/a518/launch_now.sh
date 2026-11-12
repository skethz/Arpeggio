#!/bin/bash
# A5.18 part 1 (PROTOCOL_A518.md §3): N1 and C2 on hostB now; S128 -> P128a; P128b after C2 ends. C1 runs on hostC (launched separately).
set -u
R=<SCRATCH>/antiphase_asic_20261017; F=$R/flow_v2_20261024; O=$R/a518
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
log(){ echo "$(date -u +%FT%TZ) $*" >> $O/RUNLOG.txt; }
# N1: Chord D64 at 1.15 ns
M64="$(cat $F/macros_ape_d64.txt)"; S64=$R/ape/syn/v14_d64_p1000
python3 $F/sdc_scale.py $S64/out/final.sdc $O/sdc/ape_d64_p1150.sdc 1150
log "launch N1 pnr ape_d64_p1150 (Chord) hostB cpus 8-15 syn $(sha256sum $S64/out/netlist.v | cut -c1-12)"
setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/ape_d64_p1150 $S64 ape_engine_D64_A4_SEEDL2 "$M64" 0.6 8 final 43200 8-15 $O/sdc/ape_d64_p1150.sdc > $O/logs/pnr_ape_d64_p1150.out 2>&1 < /dev/null &
# C2: closure pass on Arpeggio D64 1.00 ns
log "launch C2 closure fa_d64_p1000 hostB cpus 16-23"
setsid nohup nice -n 5 $F/run_closure.sh $F $O/closure/fa_d64_p1000_cl $R/fa_a511/pnr/fa_d64_p1000/db/final.enc.dat ape_engine_D64_A4_SEEDL2 21600 16-23 > $O/logs/closure_fa_d64_p1000.out 2>&1 < /dev/null &
# S128 -> P128a, P128b
setsid nohup $O/chain_d128.sh > $O/logs/chain_d128.out 2>&1 < /dev/null &
log "launch chain_d128 (S128 hostB cpus 0-5)"
