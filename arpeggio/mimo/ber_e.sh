#!/usr/bin/env bash
# Milestone E held-out BER (PROTOCOL_E.md): more seeds for milestone D's comparison grid (seeds 43, 44; seed 41 was D's)
# and for the matched-BER points P1-P4 (seeds 47, 48; seed 42 was D's), same methods and n as D plus the AHC rungs and
# one-stage rungs the matched-BER claims need; the copy-alternation ablation at P1-P3 on seed 47.
# Usage: ber_e.sh PART UUID, PART = <name>_<seed>, e.g. x16_43, P1_47. Outputs results/ber_e/<part>.jsonl.
PART=$1; export MIMO_GPU_UUID=$2 CUDA_VISIBLE_DEVICES=$2 NUMBA_NUM_THREADS=${NUMBA_NUM_THREADS:-48}
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_e; mkdir -p $O
echo "part $PART on $MIMO_GPU_UUID ($(nvidia-smi --query-gpu=index --format=csv,noheader -i $MIMO_GPU_UUID)) at $(date '+%H:%M:%S %Z')"
M16='{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}'
MQ='{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}'
E16=e:15,e:20,e:25,e:30
EQ=e:6,e:8,e:10,e:12,e:14
NAME=${PART%_*}; SEED=${PART##*_}
abl() { if [ "$SEED" = 47 ]; then printf ",mdiabli%d,mdiablii%d,mdiabliii%d,mdiabliv%d" $1 $1 $1 $1; fi; }
case $NAME in
x16)    python run_ber_d.py --nt 16 --M 16 --snrs $E16 --n 8000 --batch 2000 --seed $SEED --mdi $M16 --out $O/$PART \
          --methods mmse,mmseb,kbest32,pimi64,pimi256,aned32,aned64,mdiane64 ;;
x16ahc) python run_ber_d.py --nt 16 --M 16 --snrs $E16 --n 8000 --batch 2000 --seed $SEED --mdi $M16 --out $O/$PART \
          --methods mdiahc64 ;;
x8)     python run_ber_d.py --nt 8 --M 16 --snrs $E16 --n 16000 --batch 4000 --seed $SEED --mdi $M16 --out $O/$PART \
          --methods mmse,mmseb,kbest32,pimi32,pimi128,aned32,aned64,mdiane64,mdiahc64 ;;
q16)    python run_ber_d.py --nt 16 --M 4 --snrs $EQ --n 16000 --batch 4000 --seed $SEED --mdi $MQ --out $O/$PART \
          --methods mmse,kbest32,pimi32,pimi64,pimi128,pimiA32,pimiA128,aned32,aned64,mdiane64,mdiahc64 ;;
q8)     python run_ber_d.py --nt 8 --M 4 --snrs $EQ --n 16000 --batch 4000 --seed $SEED --mdi $MQ --out $O/$PART \
          --methods mmse,kbest32,pimi16,pimi64,pimiA16,pimiA64,aned32,aned64,mdiane64,mdiahc64 ;;
P1)     python run_ber_d.py --nt 16 --M 16 --snrs 20 --n 8000 --batch 2000 --seed $SEED --mdi $M16 --out $O/$PART \
          --methods mmse,kbest32,pimi64,pimi256,mdiane16,mdiane32,mdiahc32,mdiahc64,aned64$(abl 32) ;;
P2)     python run_ber_d.py --nt 32 --M 16 --snrs 22 --n 4000 --batch 1000 --seed $SEED --mdi $M16 --out $O/$PART \
          --methods mmse,kbest32,pimi128,pimi512,mdiane8,mdiahc16,mdiahc32,aned64$(abl 8) ;;
P3)     python run_ber_d.py --nt 32 --M 4 --snrs 14 --n 8000 --batch 4000 --seed $SEED --mdi $MQ --out $O/$PART \
          --methods mmse,kbest32,pimi64,pimi256,pimiA64,pimiA256,mdiane8,mdiahc32,mdiahc64,aned64$(abl 8) ;;
P4)     python run_ber_d.py --nt 16 --M 16 --snrs e:25 --n 16000 --batch 2000 --seed $SEED --mdi $M16 --out $O/$PART \
          --methods mmse,mmseb,kbest32,pimi64,pimi256,mdiane8,aned2,aned4,aned8,mdiahc64 ;;
esac 2>&1 | grep -v Warn
echo PART_DONE $(date '+%H:%M:%S %Z')
