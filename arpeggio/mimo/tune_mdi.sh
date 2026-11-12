#!/usr/bin/env bash
# MDI-Anechoic schedule on the tuning set (seed 1000), 16x16 16-QAM at 18 and 20 dB, MDI wrapper at Table I's
# 16x16 setting (Ns 64, R_max 3, S 8, MMSE and MMSE-SIC guesses); MDI-AHC (published, untuned) on the same draws.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/tune_mdi; mkdir -p $O
C="python run_ber.py --nt 16 --nr 16 --M 16 --snrs 18,20 --n 1000 --batch 1000 --seed 1000"
$C --methods mmse,sic,mdiahc --out $O/x16 2>&1 | grep -v Warn
for Sk in 64 128; do for t in 0.2 0.3 0.45; do for q in 0.25 0.4 0.6; do
  $C --methods mdiane --mdiane "{\"Sk\":$Sk,\"t0\":$t,\"t1\":$t,\"q\":$q,\"kappa\":0}" --out $O/x16 2>&1 | grep -v Warn
done; done; done
echo TUNE_MDI_DONE
