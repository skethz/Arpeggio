#!/usr/bin/env bash
# A5.16 gate G4 (PROTOCOL_A516.md section 4): run_a516.py V0 with the sm_120 cubin on batch 0 at P4, P2, P1; compare with A5.13 (hostA).
A=<SCRATCH>/ap_ber_20261024
export FAFX_CUBIN=$A/build/fa_fx_sm120.cubin
R=$A/results/a514/a516g4
python src/run_a516.py $R --tag x64 --nt 64 --M 16 --snr 22 --seed 344 --B 500 --b0 0 --b1 1 --pick abl_far_64_0.1_0.1_0_bal_8 --threads 4
python src/run_a516.py $R --tag x32 --nt 32 --M 16 --snr 22 --seed 102 --B 1000 --b0 0 --b1 1 --pick abl_far_32_0.1_0.1_0_rand_8 --threads 4
python src/run_a516.py $R --tag x16 --nt 16 --M 16 --snr 20 --seed 102 --B 2000 --b0 0 --b1 1 --pick abl_far_64_0.1_0.1_0_rand_32 --threads 4
python - <<'PY'
import numpy as np, json
A='<SCRATCH>/ap_ber_20261024/results/a514'
out={}
for t,m,s in (('x64','fafx_64_0.1_0.1_0_bal_8','snr_22.00'),('x32','fafx_32_0.1_0.1_0_rand_8','snr_22.00'),('x16','fafx_64_0.1_0.1_0_rand_32','snr_20.00')):
    a=np.load('%s/a516g4/%s/%s/%s/b00000.npz'%(A,t,m,s)); b=np.load('%s/a513_fixed/%s/%s/%s/b00000.npz'%(A,t,m,s))
    same=bool(np.array_equal(a['biterr'],b['biterr']) and np.array_equal(a['xhat'],b['xhat']))
    diff=int((a['biterr']!=b['biterr']).sum())
    ia,ib=json.loads(str(a['info'])),json.loads(str(b['info']))
    out[t]=dict(identical=same, uses_differ=diff, uses=len(a['biterr']), cnt_same=ia['cnt']==ib['cnt'], coef_same=ia['coef']==ib['coef'])
    print(t,out[t])
json.dump(out,open(A+'/gate_G4.json','w'),indent=1)
PY
