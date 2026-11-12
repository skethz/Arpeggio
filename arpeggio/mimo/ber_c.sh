#!/usr/bin/env bash
# Milestone C BER on fresh held-out seeds (PyTorch MDI wrapper, both solvers). Usage: ber_c.sh PART UUID
# Parts: x16a, x16b_ahc, x16b_ane, x32a, x32b_ahc, x32b_ane, q32a, q32b, x64c. Outputs results/ber_c/*.jsonl.
PART=$1; export MIMO_GPU_UUID=$2
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_c; mkdir -p $O
echo "part $PART on $MIMO_GPU_UUID ($(nvidia-smi --query-gpu=index --format=csv,noheader -i $MIMO_GPU_UUID)) at $(date '+%H:%M %Z')"
MA='{"Sk": 128, "kappa": 0, "q": 0.4, "t0": 0.3, "t1": 0.3}'
M16='{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}'
M32='{"Ns":128,"Rmax":3,"S":8,"guesses":["mmse","sic"]}'
MQ='{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}'
LA=mdiahc8,mdiahc16,mdiahc32,mdiahc64,mdiahc128,mdiahc256
LN=mdiane8,mdiane16,mdiane32,mdiane64,mdiane128,mdiane256
X16="--nt 16 --nr 16 --M 16 --n 8000 --batch 2000 --mdi $M16 --mdiane"
X32="--nt 32 --nr 32 --M 16 --n 4000 --batch 1000 --mdi $M32 --mdiane"
Q32="--nt 32 --nr 32 --M 4 --n 8000 --batch 4000 --mdi $MQ --mdiane"
case $PART in
x16a) python run_ber.py $X16 "$MA" --snrs 18,20,22 --seed 11 --methods mmse,sic,kbest32,mdiahc64,mdiane64 --out $O/x16_a ;;
x16b_ahc) python run_ber.py $X16 "$MA" --snrs 20 --seed 12 --methods mmse,sic,kbest32,$LA --out $O/x16_b_ahc ;;
x16b_ane) python run_ber.py $X16 "$MA" --snrs 20 --seed 12 --methods mmse,$LN --out $O/x16_b_ane ;;
x32a) python run_ber.py $X32 "$MA" --snrs 18,20,22 --seed 11 --methods mmse,sic,kbest32,mdiahc128,mdiane128 --out $O/x32_a ;;
x32b_ahc) python run_ber.py $X32 "$MA" --snrs 22 --seed 12 --methods mmse,sic,kbest32,$LA --out $O/x32_b_ahc ;;
x32b_ane) python run_ber.py $X32 "$MA" --snrs 22 --seed 12 --methods mmse,$LN --out $O/x32_b_ane ;;
q32a) python run_ber.py $Q32 "$MA" --snrs 10,12 --seed 11 --methods mmse,kbest32,mdiahc64,mdiane64 --out $O/q32_a ;;
q32b) python run_ber.py $Q32 "$MA" --snrs 14 --seed 12 --methods mmse,kbest32,$LA,$LN --out $O/q32_b ;;
x64c) python run_ber.py --nt 64 --nr 64 --M 16 --n 1562 --batch 1562 --mdi '{"Ns":8,"Rmax":3,"S":8,"guesses":["mmse","sic"]}' --mdiane "$MA" --snrs 22 --seed 13 --methods mmse,sic,kbest32,mdiahc8,mdiane8 --out $O/x64_c ;;
esac 2>&1 | grep -v Warn
echo PART_DONE $(date '+%H:%M %Z')
