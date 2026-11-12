#!/usr/bin/env bash
# Held-out uncoded BER sweeps (seed 1; the tuning set is seed 1000), per configuration with its tuned Anechoic schedule
# (results/tune3, best per configuration) and CIM's tuned unpublished parameters (results/tune2). The correlated case
# reuses 16x16 16-QAM's schedules.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_seed1; mkdir -p $O
B="python run_ber.py --seed 1 --batch 2000"
$B --nt 16 --nr 16 --M 4 --snrs 2,4,6,8,10,12,14,16 --n 32000 --methods mmse,sd,kbest32,cim16,cim64,ahc16,ahc64,ane16,ane64 \
   --ane '{"S":128,"t0":0.7,"t1":0.5,"q":0.6,"kappa":0}' --cim-as 1 --cim-pump time --out $O/q16 > $O/q16.log 2>&1
$B --nt 16 --nr 16 --M 16 --snrs 12,14,16,18,20,22,24,26,28 --n 16000 --methods mmse,sd,kbest32,cim16,cim64,ahc16,ahc64,ane16,ane64 \
   --ane '{"S":128,"t0":0.5,"t1":0.5,"q":0.6,"kappa":0}' --cim-as 1.5 --cim-pump time --out $O/x16 > $O/x16.log 2>&1
$B --nt 32 --nr 32 --M 4 --snrs 2,4,6,8,10,12,14,16 --n 16000 --methods mmse,kbest32,cim16,cim64,ahc16,ahc64,ane16,ane64 \
   --ane '{"S":128,"t0":0.5,"t1":0.4,"q":0.4,"kappa":0}' --cim-as 1 --cim-pump time --out $O/q32 > $O/q32.log 2>&1
$B --nt 32 --nr 32 --M 16 --snrs 12,14,16,18,20,22,24,26,28 --n 8000 --methods mmse,kbest32,cim16,cim64,ahc16,ahc64,ane16,ane64 \
   --ane '{"S":128,"t0":0.3,"t1":0.3,"q":0.25,"kappa":0}' --cim-as 1.5 --cim-pump time --out $O/x32 > $O/x32.log 2>&1
$B --nt 16 --nr 16 --M 16 --rho 0.5 --snrs 14,17,20,23,26,29,32 --n 16000 --methods mmse,kbest32,cim64,ahc64,ane16,ane64 \
   --ane '{"S":128,"t0":0.5,"t1":0.5,"q":0.6,"kappa":0}' --cim-as 1.5 --cim-pump time --out $O/x16_rho05 > $O/x16_rho05.log 2>&1
echo SWEEP_DONE
