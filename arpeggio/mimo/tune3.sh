#!/usr/bin/env bash
# Round 3 (tuning set): Anechoic temperatures past round 2's t1 edge, constant-T schedules (t1 = t0), and the online
# correction at larger lambda and pinning q.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; mkdir -p ../results/tune3
G='{"t0":[0.3,0.4,0.5,0.7,1.0],"t1":[0.3,0.4,0.5,0.6],"q":[0.25,0.4,0.6],"kappa":[0],"lam":[0,0.2,0.5,1.0]}'
run() { python tune.py "$@" 2>&1 | grep -v Warn > /dev/null; }
for cfg in "16 4 10,12 2000 q16" "16 16 20,24 2000 x16" "32 4 10,12 1000 q32" "32 16 20,24 1000 x32"; do
  set -- $cfg
  run --nt $1 --nr $1 --M $2 --snrs $3 --n $4 --na 64 --which ane --grid "$G" --out ../results/tune3/ane_$5
done
echo TUNE3_DONE
