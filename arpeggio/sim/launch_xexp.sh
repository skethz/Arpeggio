#!/usr/bin/env bash
# A3 exploratory workers on hostB GPU0 and GPU2 (2 each, 2 threads): plan results/plan_hostb_xexp.json. Idempotent.
A=<SCRATCH>/ap_ber_20261024
PLAN=${1:-plan_hostb_xexp.json}
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID>)
for i in ${GPUS:-0 2}; do for w in a b; do
  name=x${i}${w}
  if pgrep -f "runner.py .*--worker $name( |$)" > /dev/null; then echo "$name already running"; continue; fi
  ( export MIMO_GPU_UUID=${G[$i]}; source $A/env_hostb.sh
    nohup python -u src/runner.py --plan $A/results/${PLAN:-plan_hostb_xexp.json} --root $A/results --worker $name --cpu-jobs no \
      --threads 2 >> $A/logs/worker_$name.log 2>&1 & echo "started $name pid $!" )
done; done
