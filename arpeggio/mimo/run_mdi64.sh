#!/usr/bin/env bash
# 64x64 16-QAM with MDI (Princeton's massive-MIMO setting Ns 8, R_max 3, S 8; AHC and Anechoic) next to K-best 32/256
# and single-stage Anechoic-dDI 16/128, on held-out seed 3 (other draws than the main sweep), 20-23 dB. GPU6.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src
python run_scale.py --nt 64 --nr 64 --M 16 --snrs 20,21,22,23 --n 1562 --batch 1562 --seed 3 --K 32,256 --R 16,128 \
  --sched '{"S": 256, "t0": 0.2, "t1": 0.2, "q": 0.25, "kappa": 0.0}' --mdi mdiane8,mdiahc8 --mdiane '{"Sk": 128, "kappa": 0, "q": 0.4, "t0": 0.3, "t1": 0.3}' \
  --cubin ../build/ane_v2.cubin --out ../results/ber_scale_mdi64/x64x64_seed3 2>&1 | grep -v Warn
