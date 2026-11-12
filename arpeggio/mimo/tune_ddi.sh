#!/usr/bin/env bash
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/tune_ddi
G='{"S":[128,256],"t0":[0.2,0.3,0.4,0.6],"t1":[0.1,0.15,0.2,0.3],"q":[0.2,0.3,0.4,0.6],"kappa":[0,0.3],"lam":[0,0.3]}'
python tune_ddi.py --nt 16 --snrs 20,24 --n 2000 --na 64 --grid "$G" --out $O/r2_x16 2>&1 | grep -v Warn
python tune_ddi.py --nt 32 --snrs 20,24 --n 1000 --na 64 --grid "$G" --out $O/r2_x32 2>&1 | grep -v Warn
echo TUNE_DDI_DONE
