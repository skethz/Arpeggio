#!/usr/bin/env bash
# BER equivalence of the fixed-point kernel and the float reference on the same held-out draws (seed 1).
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/kernel_equiv; mkdir -p $O
C=$R/build/ane_v1.cubin
python fxdetect.py --cubin $C --out $O/q16 --cfg q16 --snrs 10,12,14 --n 32000 --batch 8000 --seed 1 --anneals 16,64 --float 2>&1 | grep -v Warn
python fxdetect.py --cubin $C --out $O/x16 --cfg x16 --snrs 20,22,24 --n 16000 --batch 4000 --seed 1 --anneals 16,64 --float 2>&1 | grep -v Warn
echo EQUIV_DONE
