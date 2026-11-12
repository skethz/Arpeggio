#!/usr/bin/env bash
# Coded BLER (held-out seed 1) at two 5G NR LDPC rates. Calibration factors alpha come from the tuning set
# (results/calib: calib_all.sh, and the dDI detectors below), capped to [0.01, 1] (ledger ruling); soft MMSE is used
# as it is.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src; O=../results/coded; C=../results/calib; mkdir -p $O
QA='{"S":128,"t0":0.7,"t1":0.5,"q":0.6,"kappa":0}'; QS='{"S":128,"t_abs":0.5,"q":0.6,"reg":true}'
XD='{"S":256,"t0":0.3,"t1":0.3,"q":0.4,"kappa":0,"phases":2}'
python calib.py --nt 16 --nr 16 --M 16 --snrs 13,14 --n 4000 --methods aned64,ahcd64 --aned "$XD" --out $C/x16_r12_ddi 2>&1 | grep -v Warn
python calib.py --nt 16 --nr 16 --M 16 --snrs 22,23 --n 4000 --methods aned64,ahcd64 --aned "$XD" --out $C/x16_r56_ddi 2>&1 | grep -v Warn
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
AQ12=$(alpha $C/q16_r12.jsonl); AQ56=$(alpha $C/q16_r56.jsonl)
AX12=$(alpha $C/x16_r12.jsonl $C/x16_r12_ddi.jsonl); AX56=$(alpha $C/x16_r56.jsonl $C/x16_r56_ddi.jsonl)
echo "alpha q16 r1/2 $AQ12"; echo "alpha q16 r5/6 $AQ56"; echo "alpha x16 r1/2 $AX12"; echo "alpha x16 r5/6 $AX56"
S="python soft.py --seed 1 --nt 16 --nr 16"
$S --M 4 --snrs 4,4.5,5,5.5,6 --frames 400 --fbatch 20 --k 1024 --methods mmse,kbest32,ane64,sane64,cim64,hard:ane64 --ane "$QA" --sane "$QS" --cim-as 1 --alpha "$AQ12" --out $O/q16_r12 > $O/q16_r12.log 2>&1
$S --M 4 --snrs 10,11,12,13,14 --frames 400 --fbatch 20 --k 1704 --methods mmse,kbest32,ane64,sane64,cim64,hard:ane64 --ane "$QA" --sane "$QS" --cim-as 1 --alpha "$AQ56" --out $O/q16_r56 > $O/q16_r56.log 2>&1
$S --M 16 --snrs 13,13.5,14,14.5,15 --frames 300 --fbatch 20 --k 1024 --methods mmse,kbest32,aned64,ahcd64,hard:aned64 --aned "$XD" --cim-as 1.5 --alpha "$AX12" --out $O/x16_r12 > $O/x16_r12.log 2>&1
$S --M 16 --snrs 20,21,22,23,24 --frames 300 --fbatch 20 --k 1704 --methods mmse,kbest32,aned64,ahcd64,hard:aned64 --aned "$XD" --cim-as 1.5 --alpha "$AX56" --out $O/x16_r56 > $O/x16_r56.log 2>&1
echo CODED_DONE
