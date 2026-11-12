#!/usr/bin/env bash
# Milestone D held-out BER (PROTOCOL_D.md), PyTorch implementations, same draws for every method of a part.
# Usage: ber_d.sh PART UUID. Outputs results/ber_d/<part>.jsonl. Seed 41: comparison at their published operating
# points (their Eb/N0 grid, e: prefix); seed 42: the matched-BER ladders and the ablation at P1-P4.
PART=$1; export MIMO_GPU_UUID=$2 CUDA_VISIBLE_DEVICES=$2 NUMBA_NUM_THREADS=${NUMBA_NUM_THREADS:-48}
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_d; mkdir -p $O
echo "part $PART on $MIMO_GPU_UUID ($(nvidia-smi --query-gpu=index --format=csv,noheader -i $MIMO_GPU_UUID)) at $(date '+%H:%M:%S %Z')"
M16='{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}'          # Singh et al. 2024 Table I, 16x16 (and 32x32 16-QAM)
MQ='{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}'                 # QPSK: DI-MIMO, one stage around MMSE
E16=e:15,e:20,e:25,e:30
EQ=e:6,e:8,e:10,e:12,e:14
ABLS="mdiabli%d,mdiablii%d,mdiabliii%d,mdiabliv%d"
abl() { printf "$ABLS" $1 $1 $1 $1; }
case $PART in
# ---- comparison 1, seed 41 (their operating points; 64-QAM is outside our pipeline)
x16_a)   python run_ber_d.py --nt 16 --M 16 --snrs $E16 --n 8000 --batch 2000 --seed 41 --mdi $M16 --out $O/x16_a \
           --methods mmse,mmseb,kbest32,pimi64,pimi256,aned32,aned64,mdiane64 ;;
x16_ahc) python run_ber_d.py --nt 16 --M 16 --snrs $E16 --n 8000 --batch 2000 --seed 41 --mdi $M16 --out $O/x16_ahc \
           --methods mdiahc64 ;;
x8_a)    python run_ber_d.py --nt 8 --M 16 --snrs $E16 --n 16000 --batch 4000 --seed 41 --mdi $M16 --out $O/x8_a \
           --methods mmse,mmseb,kbest32,pimi32,pimi128,aned32,aned64,mdiane64,mdiahc64 ;;
q16_a)   python run_ber_d.py --nt 16 --M 4 --snrs $EQ --n 16000 --batch 4000 --seed 41 --mdi $MQ --out $O/q16_a \
           --methods mmse,kbest32,pimi32,pimi64,pimi128,pimiA32,pimiA128,aned32,aned64,mdiane64,mdiahc64 ;;
q8_a)    python run_ber_d.py --nt 8 --M 4 --snrs $EQ --n 16000 --batch 4000 --seed 41 --mdi $MQ --out $O/q8_a \
           --methods mmse,kbest32,pimi16,pimi64,pimiA16,pimiA64,aned32,aned64,mdiane64,mdiahc64 ;;
# ---- matched-BER ladders and ablation, seed 42
P1_b)    python run_ber_d.py --nt 16 --M 16 --snrs 20 --n 8000 --batch 2000 --seed 42 --mdi $M16 --out $O/P1_b \
           --methods mmse,kbest32,pimi64,pimi256,mdiane8,mdiane16,mdiane32,mdiane64,$(abl 32) ;;
P2_b)    python run_ber_d.py --nt 32 --M 16 --snrs 22 --n 4000 --batch 1000 --seed 42 --mdi $M16 --out $O/P2_b \
           --methods mmse,kbest32,pimi128,pimi512,mdiane8,mdiane16,$(abl 8) ;;
P3_b)    python run_ber_d.py --nt 32 --M 4 --snrs 14 --n 8000 --batch 4000 --seed 42 --mdi $MQ --out $O/P3_b \
           --methods mmse,kbest32,pimi64,pimi256,pimiA64,pimiA256,mdiane8,mdiane64,$(abl 8) ;;
P4_b)    python run_ber_d.py --nt 16 --M 16 --snrs e:25 --n 16000 --batch 2000 --seed 42 --mdi $M16 --out $O/P4_b \
           --methods mmse,mmseb,kbest32,pimi64,pimi256,mdiane8,mdiane16,mdiane32,mdiane64,aned1,aned2,aned4,aned8,aned16,aned32,aned64,$(abl 8) ;;
esac 2>&1 | grep -v Warn
echo PART_DONE $(date '+%H:%M:%S %Z')
