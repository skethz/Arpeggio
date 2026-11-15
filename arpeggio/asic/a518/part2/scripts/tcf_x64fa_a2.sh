#!/bin/bash
# A5.18 amendment A5 / part 2 W2: TCF of the x64fa_a2 SAIF on S128bal's synthesis DB (as chain_x64rsb.sh). usage: tcf_x64fa_a2.sh <cpu list>
set -u
R=<SCRATCH>/antiphase_asic_20261017; P=$R/a518/part2; C=$1
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config XDG_CACHE_HOME=$R/home/.cache
log(){ echo "$(date -u +%FT%TZ) $*" >> $R/a518/RUNLOG.txt; }
SAIF=$P/act/x64fa_a2/p2/act_x64fa_a2.saif; DB=$R/a518/syn/fa_d128bal_a2_p1000/out/opt.db
[ -s $SAIF ] || { log "tcf x64fa_a2: no SAIF"; exit 1; }
log "start tcf x64fa_a2 on S128bal opt.db (fa_d128bal_a2_p1000) saif $(sha256sum $SAIF | cut -c1-12) cpus $C"
taskset -c $C nice -n 10 $R/flow/run_power.sh $DB $SAIF tb_ape/dut 1 $P/tcf/x64fa_a2
log "end tcf x64fa_a2 $(tail -1 $P/tcf/x64fa_a2.stdout 2>/dev/null) tcf $(sha256sum $P/tcf/x64fa_a2_netlist.tcf 2>/dev/null | cut -c1-12)"
