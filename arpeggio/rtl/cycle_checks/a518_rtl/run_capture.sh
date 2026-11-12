#!/usr/bin/env bash
# A5.18 part 2 W1 capture on GPU3 (UUID-checked by env_hostb_a514.sh), CPUs 0-23, nice 19.
A=<SCRATCH>/ap_ber_20261024; W=$A/a518_rtl
export MIMO_GPU_UUID=<GPU_UUID> PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TMPDIR=$W/tmp
source $A/env_hostb_a514.sh >/dev/null
export PYTHONPATH=$W/src:$A/src:$A/code_mimo/src
cd $W && exec taskset -c 0-23 nice -n 19 python src/capture_a518.py $W/capture_x64_9600.pt
