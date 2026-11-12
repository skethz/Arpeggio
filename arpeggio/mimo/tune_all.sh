#!/usr/bin/env bash
# Tuning set (seed 1000): CIM's unpublished parameters (best for the baseline) and Anechoic's schedule, per configuration.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; mkdir -p ../results/tune
run() { python tune.py "$@" 2>&1 | grep -v Warn > /dev/null; }
run --nt 16 --nr 16 --M 4 --snrs 10,12 --n 2000 --na 64 --which cim --out ../results/tune/cim_q16
run --nt 16 --nr 16 --M 4 --snrs 10,12 --n 2000 --na 64 --which ane --out ../results/tune/ane_q16
run --nt 16 --nr 16 --M 16 --snrs 20,24 --n 2000 --na 64 --which cim --out ../results/tune/cim_x16
run --nt 16 --nr 16 --M 16 --snrs 20,24 --n 2000 --na 64 --which ane --out ../results/tune/ane_x16
run --nt 32 --nr 32 --M 4 --snrs 10,12 --n 1000 --na 64 --which cim --out ../results/tune/cim_q32
run --nt 32 --nr 32 --M 4 --snrs 10,12 --n 1000 --na 64 --which ane --out ../results/tune/ane_q32
run --nt 32 --nr 32 --M 16 --snrs 20,24 --n 1000 --na 64 --which cim --out ../results/tune/cim_x32
run --nt 32 --nr 32 --M 16 --snrs 20,24 --n 1000 --na 64 --which ane --out ../results/tune/ane_x32
echo TUNE_DONE
