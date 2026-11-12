#!/usr/bin/env bash
source <SCRATCH>/ap_ber_20261024/env_ap.sh
export NUMBA_NUM_THREADS=32
mkdir -p logs/smoke
nohup python src/smoke_tput.py x16,x16ns8,q32,q16 > logs/smoke/tput_gpu_a.log 2>&1 &
nohup python src/smoke_tput.py x32 > logs/smoke/tput_gpu_b.log 2>&1 &
nohup python src/smoke_tput.py kb16,kb32,sd16,sd16q > logs/smoke/tput_cpu.log 2>&1 &
sleep 2; echo launched
