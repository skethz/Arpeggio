#!/usr/bin/env bash
# Milestone B goal 1: held-out (seed 1) sweeps with MDI-MIMO (AHC, Table I settings) and MDI-Anechoic (ours; the
# tune_mdi schedule with the lowest summed BER at 18 and 20 dB), next to MMSE, MMSE-SIC, K-best 32 and the single-stage
# Anechoic-dDI-64 of milestone A, on the same draws; plus DI-MIMO for QPSK (Sec. V-B: one stage, MMSE guess, R_max 1).
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/ber_seed1_mdi; mkdir -p $O
while [ ! -s ../logs/tune_mdi.exit ]; do sleep 30; done
MA=$(python3 - <<'PY'
import json
s = {}
for l in open('../results/tune_mdi/x16.jsonl'):
    r = json.loads(l)
    if r['method'] == 'mdiane':
        k = json.dumps(r['mdiane'], sort_keys=True)
        s[k] = s.get(k, 0.0) + r['ber']
print(min(s, key=s.get))
PY
)
echo "MDI-Anechoic schedule: $MA"
X16D='{"S":256,"t0":0.3,"t1":0.3,"q":0.4,"kappa":0,"phases":2}'
X32D='{"S":256,"t0":0.3,"t1":0.2,"q":0.4,"kappa":0.3,"phases":2}'
python run_ber.py --nt 16 --nr 16 --M 16 --snrs 12,14,16,18,20,22,24,26,28 --n 8000 --batch 2000 --seed 1 \
  --methods mmse,sic,kbest32,aned64,mdiahc8,mdiane8,mdiane,mdiahc --aned "$X16D" \
  --mdi '{"Ns":64,"Rmax":3,"S":8,"guesses":["mmse","sic"]}' --mdiane "$MA" --out $O/x16 2>&1 | grep -v Warn
python run_ber.py --nt 16 --nr 16 --M 4 --snrs 6,8,10,12,14,16 --n 16000 --batch 4000 --seed 1 \
  --methods mmse,kbest32,ane64,mdiahc64,mdiane64 --ane '{"S":128,"t0":0.7,"t1":0.5,"q":0.6,"kappa":0}' \
  --mdi '{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}' --mdiane "$MA" --out $O/q16 2>&1 | grep -v Warn
python run_ber.py --nt 32 --nr 32 --M 4 --snrs 6,8,10,12,14,16 --n 8000 --batch 4000 --seed 1 \
  --methods mmse,kbest32,ane64,mdiahc64,mdiane64 --ane '{"S":128,"t0":0.5,"t1":0.4,"q":0.4,"kappa":0}' \
  --mdi '{"Ns":64,"Rmax":1,"S":1,"guesses":["mmse"]}' --mdiane "$MA" --out $O/q32 2>&1 | grep -v Warn
python run_ber.py --nt 32 --nr 32 --M 16 --snrs 14,16,18,20,22,24,26 --n 4000 --batch 1000 --seed 1 \
  --methods mmse,sic,kbest32,aned64,mdiahc8,mdiane8,mdiane,mdiahc --aned "$X32D" \
  --mdi '{"Ns":128,"Rmax":3,"S":8,"guesses":["mmse","sic"]}' --mdiane "$MA" --out $O/x32 2>&1 | grep -v Warn
echo SWEEP_MDI_DONE
