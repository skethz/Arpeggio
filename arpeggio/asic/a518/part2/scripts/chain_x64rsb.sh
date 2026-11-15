#!/bin/bash
# A5.18 part 2, used if the balanced-start check fails: activity of the random-start build (arpeggio_engine.sv, no ENGINE_ARPEGGIO_BAL)
# on stim_x64arpeggio, then its TCF on the S128 synthesis DB (arpeggio_d128_p1000). hostB CPUs 8-11, nice 10.
set -u
R=<SCRATCH>/arpeggio_asic_20261017; P=$R/a518/part2; S=$P/scripts
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
log(){ echo "$(date -u +%FT%TZ) $*" >> $R/a518/RUNLOG.txt; }
taskset -c 8-11 nice -n 10 bash $S/act_run_a518.sh x64arpeggio_rsb $R/chord/rtl/arpeggio_engine.sv <SCRATCH>/arpeggio_ber_20261024/a518_rtl/runs/stim_x64arpeggio 128 4 || exit 1
grep -q 'OK' $P/act/x64arpeggio_rsb/pass1.txt || { log "act x64arpeggio_rsb pass 1 not OK; no TCF"; exit 1; }
SAIF=$P/act/x64arpeggio_rsb/p2/act_x64arpeggio_rsb.saif; [ -s $SAIF ] || { log "act x64arpeggio_rsb: no SAIF"; exit 1; }
mkdir -p $P/tcf
log "start tcf x64arpeggio_rsb on S128 opt.db (arpeggio_d128_p1000) cpus 8-11"
taskset -c 8-11 nice -n 10 $R/flow/run_power.sh $R/a518/syn/arpeggio_d128_p1000/out/opt.db $SAIF tb_engine/dut 1 $P/tcf/x64arpeggio_rsb
log "end tcf x64arpeggio_rsb $(tail -1 $P/tcf/x64arpeggio_rsb.stdout 2>/dev/null) tcf $(sha256sum $P/tcf/x64arpeggio_rsb_netlist.tcf 2>/dev/null | cut -c1-12)"
