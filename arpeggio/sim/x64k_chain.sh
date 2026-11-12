#!/usr/bin/env bash
# A5.6 amendment 6: K-best K on the X64 draws, CPU only, nice 10, 2 numba threads; one process per K; resumes from saved batches.
A=<SCRATCH>/ap_ber_20261024; R=$A/results/a56
export MIMO_GPU_UUID=<GPU_UUID>
source $A/env_hostb_a56.sh
export CUDA_VISIBLE_DEVICES=
K=$1
nice -n 10 python -u src/x64_kbest.py $R --K $K >> $A/logs/a56/x64k_$K.log 2>&1
echo "$(date '+%F %T') exit $? K $K" >> $A/logs/a56/x64k_chain.log
