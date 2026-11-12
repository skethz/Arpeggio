#!/bin/bash
# picks 4 idle CPUs, then power_multi_a518.sh with the given arguments (key db top period tags...)
R=<SCRATCH>/antiphase_asic_20261017; C=$(bash $R/a518/part2/scripts/pick_cpus.sh 4)
k=$1; db=$2; top=$3; ps=$4; shift 4
taskset -c $C bash $R/a518/part2/scripts/power_multi_a518.sh $k $db $top $ps $C "$@"
