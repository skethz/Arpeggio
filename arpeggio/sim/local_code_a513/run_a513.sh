#!/usr/bin/env bash
# A5.13 launch (PROTOCOL_A513.md sections 2-3): hostA GPU7 only (env_ap.sh), 4 threads per process, nice 10.
source <SCRATCH>/ap_ber_20261024/env_ap.sh > /dev/null 2>&1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
cd <SCRATCH>/ap_ber_20261024/a513
run() { nice -n 10 python src/run_a513.py "$@"; }
X16="--tag x16 --nt 16 --M 16 --snr 20 --seed 102 --B 2000"
X32="--tag x32 --nt 32 --M 16 --snr 22 --seed 102 --B 1000"
X64="--tag x64 --nt 64 --M 16 --snr 22 --seed 344 --B 500"
case "$1" in
P1)  run results $X16 --b0 0 --b1 200 --pick abl_far_64_0.1_0.1_0_rand_32 --threads 4 && \
     run hostcheck $X16 --b0 0 --b1 14 --solver prod --prod-ns 32 --threads 4 && \
     run hostcheck $X32 --b0 0 --b1 43 --solver prod --prod-ns 8 --threads 4 && \
     run hostcheck $X64 --b0 0 --b1 30 --solver prod --prod-ns 8 --threads 4 ;;
P2)  run results $X32 --b0 0 --b1 300 --pick abl_far_32_0.1_0.1_0_rand_8 --threads 4 ;;
P4a) run results $X64 --b0 0 --b1 150 --pick abl_far_64_0.1_0.1_0_bal_8 --threads 4 ;;
P4b) run results $X64 --b0 150 --b1 300 --pick abl_far_64_0.1_0.1_0_bal_8 --threads 4 ;;
P4c) run results $X64 --b0 300 --b1 450 --pick abl_far_64_0.1_0.1_0_bal_8 --threads 4 ;;
P4d) run results $X64 --b0 450 --b1 600 --pick abl_far_64_0.1_0.1_0_bal_8 --threads 4 ;;
esac
