#!/bin/bash
# Genus SAIF -> netlist TCF (flow/run_power.sh, scale 1, scope tb_ape/dut), as fa_a511/tcf_make.sh. usage: tcf_remote.sh <opt.db> <saif> <out prefix>
R=<SCRATCH>/antiphase_asic_20261017; export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config
C=$(bash $R/a518/part2/scripts/pick_cpus.sh 4)
taskset -c $C $R/flow/run_power.sh $1 $2 tb_ape/dut 1 $3
echo "cpus $C $(tail -1 $3.stdout) tcf $(sha256sum ${3}_netlist.tcf | cut -c1-12)"
