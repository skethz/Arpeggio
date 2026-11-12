#!/usr/bin/env bash
# Rate 5/6 at the list detectors' waterfalls (the first grid sat at soft MMSE's, where every list detector already
# decodes error-free): calibration refitted on the tuning set at these lower SNRs, then held-out seed 1. Starts after
# the energy cohort, so the cohort runs alone on GPU6.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/coded; C=../results/calib
while [ ! -s ../logs/cohort.exit ]; do sleep 30; done
QA='{"S":128,"t0":0.7,"t1":0.5,"q":0.6,"kappa":0}'; QS='{"S":128,"t_abs":0.5,"q":0.6,"reg":true}'
XD='{"S":256,"t0":0.3,"t1":0.3,"q":0.4,"kappa":0,"phases":2}'
python calib.py --nt 16 --nr 16 --M 4 --snrs 7,8 --n 4000 --methods kbest32,ane64,sane64,cim64 --ane "$QA" --sane "$QS" --cim-as 1 --out $C/q16_r56_low 2>&1 | grep -v Warn
python calib.py --nt 16 --nr 16 --M 16 --snrs 17,18 --n 4000 --methods kbest32,aned64,ahcd64 --aned "$XD" --out $C/x16_r56_low 2>&1 | grep -v Warn
alpha() { python3 - "$@" <<'PY'
import json, sys
out = {}
for f in sys.argv[1:]:
    for l in open(f):
        r = json.loads(l)
        if r['method'] != 'mmse':
            out[r['method']] = min(1.0, max(0.01, r['alpha']))
print(json.dumps(out))
PY
}
AQ=$(alpha $C/q16_r56_low.jsonl); AX=$(alpha $C/x16_r56_low.jsonl); echo "alpha q16 r5/6 low $AQ"; echo "alpha x16 r5/6 low $AX"
S="python soft.py --seed 1 --nt 16 --nr 16"
$S --M 4 --snrs 6,7,8,9,10 --frames 400 --fbatch 20 --k 1704 --methods kbest32,ane64,sane64,cim64,hard:ane64 --ane "$QA" --sane "$QS" --cim-as 1 --alpha "$AQ" --out $O/q16_r56_low > $O/q16_r56_low.log 2>&1
$S --M 16 --snrs 15,16,17,18,19,20 --frames 300 --fbatch 20 --k 1704 --methods kbest32,aned64,ahcd64,hard:aned64 --aned "$XD" --cim-as 1.5 --alpha "$AX" --out $O/x16_r56_low > $O/x16_r56_low.log 2>&1
echo R56B_DONE
