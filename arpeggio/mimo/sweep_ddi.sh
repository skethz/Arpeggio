#!/usr/bin/env bash
# Held-out 16-QAM sweeps on Princeton's delta formulation (dDI, K = 1), seed 1, with the dDI-tuned Anechoic schedules
# (results/tune_ddi/r2_*): Anechoic with alternating copy updates, AHC and the SDE CIM on dDI, plus MMSE and K-best 32
# on the same draws. The correlated case reuses 16x16's schedule.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_seed1_ddi; mkdir -p $O
X16='{"S":256,"t0":0.3,"t1":0.3,"q":0.4,"kappa":0,"phases":2}'; X32='{"S":256,"t0":0.3,"t1":0.2,"q":0.4,"kappa":0.3,"phases":2}'
B="python run_ber.py --seed 1 --batch 2000 --cim-as 1.5 --cim-pump time"
$B --nt 16 --nr 16 --M 16 --snrs 12,14,16,18,20,22,24,26,28 --n 16000 --methods mmse,kbest32,cimd64,ahcd16,ahcd64,aned16,aned64 --aned "$X16" --out $O/x16 > $O/x16.log 2>&1
$B --nt 32 --nr 32 --M 16 --snrs 12,14,16,18,20,22,24,26,28 --n 8000 --methods mmse,kbest32,cimd64,ahcd16,ahcd64,aned16,aned64 --aned "$X32" --out $O/x32 > $O/x32.log 2>&1
$B --nt 16 --nr 16 --M 16 --rho 0.5 --snrs 14,17,20,23,26,29,32 --n 16000 --methods mmse,kbest32,ahcd64,aned16,aned64 --aned "$X16" --out $O/x16_rho05 > $O/x16_rho05.log 2>&1
echo DDI_DONE
