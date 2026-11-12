#!/usr/bin/env bash
# A5.6 X3 chain: one production-model process at a time, nice 10; resumes from saved batches. Started once logs/a56/x3_test.ok exists.
A=<SCRATCH>/ap_ber_20261024; R=$A/results/a56
export MIMO_GPU_UUID=<GPU_UUID>
source $A/env_hostb_a56.sh
run() { nice -n 10 python -u src/x3_prod.py $R "$@" >> $A/logs/a56/x3.log 2>&1; echo "$(date '+%F %T') exit $? $*" >> $A/logs/a56/x3_chain.log; }
run --tag x32 --nt 32 --M 16 --snr 22 --ns 8 --seed 102 --B 1000 --min-vec 2000 --max-uses 300000
run --tag x16 --nt 16 --M 16 --snr 20 --ns 32 --seed 102 --B 2000 --min-vec 2000 --max-uses 400000
run --tag x64 --nt 64 --M 16 --snr 22 --ns 8 --seed 344 --B 500 --min-vec 100 --max-uses 20000
echo ALL_DONE >> $A/logs/a56/x3_chain.log
