#!/usr/bin/env bash
# Extension of the QPSK sweeps to 30 dB for the detectors that do not reach BER 1e-3 by 16 dB (seed 1; the SNR index
# seeds differ from the first sweep's, so these are other held-out draws).
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_seed1_ext; mkdir -p $O
while [ ! -s ../logs/tune_ddi.exit ]; do sleep 20; done
B="python run_ber.py --seed 1 --batch 2000"
$B --nt 16 --nr 16 --M 4 --snrs 18,20,22,24,26,28,30 --n 32000 --methods mmse,cim16,cim64,ahc16,ahc64 --cim-as 1 --cim-pump time --out $O/q16 > $O/q16.log 2>&1
$B --nt 32 --nr 32 --M 4 --snrs 18,20,22,24,26,28,30 --n 16000 --methods mmse,cim16,cim64,ahc16,ahc64 --cim-as 1 --cim-pump time --out $O/q32 > $O/q32.log 2>&1
echo EXT_DONE
