#!/usr/bin/env bash
# Round 2 on the tuning set: grids extended past round 1's edges (Anechoic t0 / t1 / q, the online form; CIM A_s).
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; mkdir -p ../results/tune2
G='{"t0":[0.15,0.25,0.35,0.5,0.7],"t1":[0.05,0.1,0.15,0.2,0.3],"q":[0,0.1,0.25,0.4],"kappa":[0],"lam":[0,0.05,0.2]}'
C='{"As":[0.2,0.35,0.5,0.7,1,1.5],"pump":["step","time"]}'
run() { python tune.py "$@" 2>&1 | grep -v Warn > /dev/null; }
for cfg in "16 4 10,12 2000 q16" "16 16 20,24 2000 x16" "32 4 10,12 1000 q32" "32 16 20,24 1000 x32"; do
  set -- $cfg
  run --nt $1 --nr $1 --M $2 --snrs $3 --n $4 --na 64 --which cim --grid "$C" --out ../results/tune2/cim_$5
  run --nt $1 --nr $1 --M $2 --snrs $3 --n $4 --na 64 --which ane --grid "$G" --out ../results/tune2/ane_$5
done
echo TUNE2_DONE
