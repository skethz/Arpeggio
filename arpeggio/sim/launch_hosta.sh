#!/usr/bin/env bash
# Starts the hostA workers: 2 GPU workers on GPU7 (untimed error counting; stopped before any timing window) and 1 CPU
# worker for K-best / sphere decoder (numba, 32 threads). Idempotent. Usage: launch_hosta.sh
A=<SCRATCH>/ap_ber_20261024
source $A/env_ap.sh
for name in z7a z7b; do
  if pgrep -f "runner.py .*--worker $name( |$)" > /dev/null; then echo "$name already running"; continue; fi
  NUMBA_NUM_THREADS=4 nohup python -u src/runner.py --plan $A/results/plan_hosta.json --root $A/results --worker $name \
    --cpu-jobs no --threads 4 >> $A/logs/worker_$name.log 2>&1 & echo "started $name pid $!"
done
name=zcpu
if pgrep -f "runner.py .*--worker $name( |$)" > /dev/null; then echo "$name already running"; else
  NUMBA_NUM_THREADS=32 nohup python -u src/runner.py --plan $A/results/plan_hosta.json --root $A/results --worker $name \
    --cpu-jobs only --threads 4 >> $A/logs/worker_$name.log 2>&1 & echo "started $name pid $!"
fi
