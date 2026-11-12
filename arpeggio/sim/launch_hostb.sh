#!/usr/bin/env bash
# Starts the hostB error-counting workers (untimed): 2 per allowed GPU, 2 threads each (12 cores of the 24 allowed).
# Idempotent: a worker name already running is not started twice. Usage: launch_hostb.sh [FILTER]
A=<SCRATCH>/ap_ber_20261024
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID>)
FILTER=${1:-}
for i in 0 1 2; do for w in a b; do
  name=m${i}${w}
  if pgrep -f "runner.py .*--worker $name( |$)" > /dev/null; then echo "$name already running"; continue; fi
  ( export MIMO_GPU_UUID=${G[$i]}; source $A/env_hostb.sh
    nohup python -u src/runner.py --plan $A/results/plan_hostb_v2.json --root $A/results --worker $name --cpu-jobs no \
      --threads 2 ${FILTER:+--filter $FILTER} >> $A/logs/worker_$name.log 2>&1 & echo "started $name pid $!" )
done; done
# CPU worker (A2): K-best / sphere decoder on hostB's CPUs, 8 numba threads (total with the GPU workers <= 24 cores)
name=mcpu
if pgrep -f "runner.py .*--worker $name( |$)" > /dev/null; then echo "$name already running"; else
  ( export MIMO_GPU_UUID=${G[0]}; source $A/env_hostb.sh; export NUMBA_NUM_THREADS=8
    nohup python -u src/runner.py --plan $A/results/plan_hostb_v2.json --root $A/results --worker $name --cpu-jobs only \
      --threads 1 >> $A/logs/worker_$name.log 2>&1 & echo "started $name pid $!" )
fi
