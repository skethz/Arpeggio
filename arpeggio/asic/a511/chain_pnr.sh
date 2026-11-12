#!/bin/bash
# A5.11 P&R chain (PROTOCOL_A511 §3): wait for synthesis, then 1.00 ns at the synthesis SDC plus pre-staged walk periods.
# usage: chain_pnr.sh <D> <SEEDL> "<hostB runs: period:cpus ...>" "<hostD runs: period:cpus ...>"
set -u
R=<SCRATCH>/antiphase_asic_20261017; F=$R/flow_v2_20261024; O=$R/fa_a511
d=$1; sl=$2; LOC=$3; REM=$4; S=$O/syn/fa_d${d}_p1000; TOP=ape_engine_D${d}_A4_SEEDL${sl}; M="$(cat $F/macros_ape_d$d.txt)"
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
until grep -q '^exit ' $S/time.log 2>/dev/null; do sleep 60; done
if ! grep -q '^exit 0' $S/time.log || [ ! -s $S/out/netlist.v ]; then echo "$(date -u +%FT%TZ) chain d$d SYN_FAILED" >> $O/RUNLOG.txt; exit 1; fi
mkdir -p $O/sdc
for spec in $LOC $REM; do p=${spec%%:*}; [ "$p" = 1000 ] || python3 $F/sdc_scale.py $S/out/final.sdc $O/sdc/fa_d${d}_p$p.sdc $p; done
echo "$(date -u +%FT%TZ) chain d$d syn done; sdc $(ls $O/sdc | tr '\n' ' ')" >> $O/RUNLOG.txt
if [ -n "$REM" ]; then
  ssh -n -o BatchMode=yes hostD "mkdir -p $O/syn $O/sdc $O/pnr" && rsync -a $S $O/syn/ < /dev/null && rsync -a $O/sdc/ hostD:$O/sdc/ < /dev/null
  rsync -a $S hostD:$O/syn/ < /dev/null
fi
mkdir -p $O/pnr
for spec in $LOC; do p=${spec%%:*}; c=${spec#*:}; X=""; [ "$p" = 1000 ] || X=$O/sdc/fa_d${d}_p$p.sdc
  echo "$(date -u +%FT%TZ) launch pnr fa_d${d}_p$p hostB cpus $c" >> $O/RUNLOG.txt
  setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/fa_d${d}_p$p $S $TOP "$M" 0.6 8 final 43200 $c $X > $O/logs/pnr_d${d}_p$p.out 2>&1 < /dev/null &
done
for spec in $REM; do p=${spec%%:*}; c=${spec#*:}; X=""; [ "$p" = 1000 ] || X=$O/sdc/fa_d${d}_p$p.sdc
  echo "$(date -u +%FT%TZ) launch pnr fa_d${d}_p$p hostD cpus $c" >> $O/RUNLOG.txt
  ssh -n -o BatchMode=yes hostD "cd $O && HOME=$R/home setsid nohup nice -n 5 $F/run_v2.sh $O/pnr/fa_d${d}_p$p $S $TOP '$M' 0.6 8 final 43200 $c $X > $O/pnr/fa_d${d}_p$p.out 2>&1 < /dev/null &"
done
wait
