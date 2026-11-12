#!/usr/bin/env bash
# Parts of sweep_mdi.sh moved to GPU0-2 (the user's permission of 11:33 CEST). Usage: sweep_mdi_part.sh PART UUID
# PART: x16 (16x16 16-QAM, moved from GPU6 at 11:48; stopped 12:17 with GPU0-3), x16a / x16b (its rerun on GPU4/5:
# 12-18 dB seed 1, 20-28 dB seed 6), qpsk (16x16 and 32x32 QPSK, DI-MIMO), x32a (32x32 16-QAM, 14-18 dB, seed 1), x32b (20-26 dB, seed 2: other
# draws, so that the two parts' SNR indices do not reuse the same channel realisations).
PART=$1; export MIMO_GPU_UUID=$2
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_seed1_mdi; mkdir -p $O
bash gpu_free.sh $MIMO_GPU_UUID || { echo "GPU $MIMO_GPU_UUID busy"; exit 4; }
echo "part $PART on $MIMO_GPU_UUID ($(nvidia-smi --query-gpu=index --format=csv,noheader -i $MIMO_GPU_UUID)) at $(date '+%H:%M %Z')"
MA='{"Sk": 128, "kappa": 0, "q": 0.4, "t0": 0.3, "t1": 0.3}'
X32D='{"S":256,"t0":0.3,"t1":0.2,"q":0.4,"kappa":0.3,"phases":2}'
X32M='{"Ns":128,"Rmax":3,"S":8,"guesses":["mmse","sic"]}'
X32="--nt 32 --nr 32 --M 16 --methods mmse,sic,kbest32,aned64,mdiahc8,mdiane8,mdiane,mdiahc --aned $X32D --mdi $X32M"
X16D='{"S":256,"t0":0.3,"t1":0.3,"q":0.4,"kappa":0,"phases":2}'
case $PART in
x16)
  python run_ber.py --nt 16 --nr 16 --M 16 --snrs 12,14,16,18,20,22,24,26,28 --n 8000 --batch 2000 --seed 1 \
    --methods mmse,sic,kbest32,aned64,mdiahc8,mdiane8,mdiane,mdiahc --aned "$X16D" \
    --mdi '{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}' --mdiane "$MA" --out $O/x16 2>&1 | grep -v Warn ;;
qpsk)
  python run_ber.py --nt 16 --nr 16 --M 4 --snrs 6,8,10,12,14,16 --n 16000 --batch 4000 --seed 1 \
    --methods mmse,kbest32,ane64,mdiahc64,mdiane64 --ane '{"S":128,"t0":0.7,"t1":0.5,"q":0.6,"kappa":0}' \
    --mdi '{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}' --mdiane "$MA" --out $O/q16 2>&1 | grep -v Warn
  python run_ber.py --nt 32 --nr 32 --M 4 --snrs 6,8,10,12,14,16 --n 8000 --batch 4000 --seed 1 \
    --methods mmse,kbest32,ane64,mdiahc64,mdiane64 --ane '{"S":128,"t0":0.5,"t1":0.4,"q":0.4,"kappa":0}' \
    --mdi '{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}' --mdiane "$MA" --out $O/q32 2>&1 | grep -v Warn ;;
x16a)
  python run_ber.py --nt 16 --nr 16 --M 16 --snrs 12,14,16,18 --n 8000 --batch 2000 --seed 1 \
    --methods mmse,sic,kbest32,aned64,mdiahc8,mdiane8,mdiane,mdiahc --aned "$X16D" \
    --mdi '{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}' --mdiane "$MA" --out $O/x16_a 2>&1 | grep -v Warn ;;
x16b)
  python run_ber.py --nt 16 --nr 16 --M 16 --snrs 20,22,24,26,28 --n 8000 --batch 2000 --seed 6 \
    --methods mmse,sic,kbest32,aned64,mdiahc8,mdiane8,mdiane,mdiahc --aned "$X16D" \
    --mdi '{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}' --mdiane "$MA" --out $O/x16_b 2>&1 | grep -v Warn ;;
x32a) python run_ber.py $X32 --snrs 14,16,18 --n 4000 --batch 1000 --seed 1 --mdiane "$MA" --out $O/x32_a 2>&1 | grep -v Warn ;;
x32b) python run_ber.py $X32 --snrs 20,22,24,26 --n 4000 --batch 1000 --seed 2 --mdiane "$MA" --out $O/x32_b 2>&1 | grep -v Warn ;;
esac
echo PART_DONE
