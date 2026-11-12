#!/bin/bash
# A5.11 §4: Genus SAIF -> netlist TCF on the engine's synthesis DB (flow/run_power.sh, scale 1, scope tb_ape/dut).
# usage: tcf_make.sh <tag p1fa|p1ap|p2fa|p2ap>
set -u
R=<SCRATCH>/antiphase_asic_20261017; O=$R/fa_a511; t=$1
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
case $t in p1fa) DB=$O/syn/fa_d32_p1000/out/opt.db;; p2fa) DB=$O/syn/fa_d64_p1000/out/opt.db;;
           p1ap) DB=$R/ape/syn/v14_d32_p1000/out/opt.db;; p2ap) DB=$R/ape/syn/v14_d64_p1000/out/opt.db;; esac
SA=$O/act/$t/p2/act_$t.saif
until [ -s $SA ] && [ -e $DB ] && grep -q "end act $t" $O/RUNLOG.txt; do sleep 60; done
echo "$(date -u +%FT%TZ) start tcf $t" >> $O/RUNLOG.txt
taskset -c 20-23 nice -n 10 $R/flow/run_power.sh $DB $SA tb_ape/dut 1 $O/power/tcf/${t}_1000
echo "$(date -u +%FT%TZ) end tcf $t $(tail -1 $O/power/tcf/${t}_1000.stdout) $(grep -o 'PW_TCF.*' $O/power/tcf/${t}_1000_genus.log | head -1 | cut -c1-40)" >> $O/RUNLOG.txt
