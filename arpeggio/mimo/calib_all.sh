#!/usr/bin/env bash
# LLR calibration on the tuning set (seed 1000) at each configuration's coded waterfall SNRs (soft-MMSE scan).
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/calib; mkdir -p $O
QA='{"S":128,"t0":0.7,"t1":0.5,"q":0.6,"kappa":0}'; XA='{"S":128,"t0":0.5,"t1":0.5,"q":0.6,"kappa":0}'
QS='{"S":128,"t_abs":0.5,"q":0.6,"reg":true}'; XS='{"S":128,"t_abs":0.5,"q":0.6,"reg":true}'
python calib.py --nt 16 --nr 16 --M 4 --snrs 4,5 --n 4000 --methods mmse,kbest32,ane64,sane64,cim64 --ane "$QA" --sane "$QS" --cim-as 1 --out $O/q16_r12 2>&1 | grep -v Warn
python calib.py --nt 16 --nr 16 --M 4 --snrs 11,12 --n 4000 --methods mmse,kbest32,ane64,sane64,cim64 --ane "$QA" --sane "$QS" --cim-as 1 --out $O/q16_r56 2>&1 | grep -v Warn
python calib.py --nt 16 --nr 16 --M 16 --snrs 13,14 --n 4000 --methods mmse,kbest32,ane64,sane64,cim64 --ane "$XA" --sane "$XS" --cim-as 1.5 --out $O/x16_r12 2>&1 | grep -v Warn
python calib.py --nt 16 --nr 16 --M 16 --snrs 22,23 --n 4000 --methods mmse,kbest32,ane64,sane64,cim64 --ane "$XA" --sane "$XS" --cim-as 1.5 --out $O/x16_r56 2>&1 | grep -v Warn
echo CALIB_DONE
