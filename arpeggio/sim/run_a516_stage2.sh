#!/usr/bin/env bash
# A5.16 stage 2 (PROTOCOL_A516.md section 3): V0, V1, V2 at P1, seed 102, batches 0-199 of 2,000 uses, one process, 4 threads, hostB.
A=<SCRATCH>/ap_ber_20261024
export FAFX_CUBIN=$A/build/fa_fx_sm120.cubin
R=$A/results/a514/a516x
P="--tag x16 --nt 16 --M 16 --snr 20 --seed 102 --B 2000 --pick abl_far_64_0.1_0.1_0_rand_32 --threads 4"
for b in $(seq 0 25 175); do
  python src/run_a516.py $R $P --b0 $b --b1 $((b+25))
  python src/run_a516.py $R $P --b0 $b --b1 $((b+25)) --qbits 16
  python src/run_a516.py $R $P --b0 $b --b1 $((b+25)) --key-tag 0xA516
done
echo STAGE2 DONE
