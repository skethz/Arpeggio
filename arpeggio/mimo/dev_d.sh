#!/usr/bin/env bash
# Development timing pass (not the cohort): tuning-seed draws, 2-s segments, one repeat. Usage: dev_d.sh UUID
export MIMO_GPU_UUID=$1; R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src
python bench_d.py --plan $R/results/bench_d_dev/PLAN_dev.json --ane-cubin $R/build/ane_v2.cubin --pimi-cubin $R/build/pimi_v1.cubin --out $R/results/bench_d_dev/dev --min-s 2 --reps 1 --idle-s 2
echo DEV_DONE $? $(date '+%H:%M:%S %Z')
