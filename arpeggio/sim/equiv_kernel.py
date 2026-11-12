#!/usr/bin/env python3
"""B200-vs-RTX 5090 kernel equivalence (PROTOCOL.md 2, E1): identical fixed-point/float inputs are built on the CPU
(device-independent), the unchanged kernels (sm_100 cubins on the B200, sm_120 rebuilds on the 5090) run them with
fixed Philox seeds / fixed start states, and the SHA-256 of every output tensor is printed. Bit-identity holds iff
the two hosts print the same digests. CPU float arithmetic differs between hosts (different CPUs / BLAS paths), so the
inputs are built once and saved (INPUTS.pt); the other host loads the same file. Usage: equiv_kernel.py OUT.json INPUTS.pt"""
import hashlib
import json
import os
import sys

import torch

import ahcfx
import anefx
import apx
import mimo
import pimi

torch.backends.cuda.matmul.allow_tf32 = False
ka = anefx.Kernel(os.environ['ANE_CUBIN'])
kh = ahcfx.AhcKernel(os.environ['AHC_CUBIN'])
kp = pimi.PimiKernel(os.environ['PIMI_CUBIN'])
H = lambda t: hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
out = dict(device=torch.cuda.get_device_name(0), cases={}, inputs={})
INP = sys.argv[2]
if os.path.exists(INP):
    store = torch.load(INP)
else:
    store = {}
    for shape, snr, K in (('x16', 20.0, 1), ('x16', 20.0, 2), ('x16', 20.0, 3), ('q32', 12.0, 1), ('q16', 12.0, 1)):
        s = apx.SHAPES[shape]
        b = apx.draw(9400, snr, K, 64, s['nt'], s['M'], dev='cpu')      # CPU problem construction
        z, _, _ = mimo.mmse(b)
        lm = mimo.quantize_levels(z / mimo._mu(b, z), s['M'])
        I = mimo.ising_delta_at(b, lm, K)
        gcpu = torch.Generator(device='cpu'); gcpu.manual_seed(77)
        x0, e0 = ahcfx.start_state(64, 6, I['h0'].shape[1] + 1, gcpu, 'cpu')
        store[(shape, snr, K)] = (I, x0, e0)
    torch.save(store, INP)
for (shape, snr, K), (I, x0, e0) in store.items():
    s = apx.SHAPES[shape]
    out['inputs']['%s_K%d' % (shape, K)] = H(I['J']) + H(I['h0'])
    F = anefx.to_fixed(I, 128 * 2 * K, 0.3, 0.3, 0.4, 0.0)
    Fc = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in F.items()}
    for P in (2 * K, 1):
        ss, ee = ka.anechoic(Fc, 12, 123456789 + K, P=P, mode='chains')
        out['cases']['ane_%s_K%d_P%d' % (shape, K, P)] = [H(ss), H(ee)]
    Ic = {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in I.items()}
    if (I['h0'].shape[1] + 1) ** 2 * 4 < 96 * 1024 or torch.cuda.get_device_capability(0)[0] == 10:
        ss, ee = kh.ahc(Ic, x0.cuda(), e0.cuda())
        out['cases']['ahc_%s_K%d' % (shape, K)] = [H(ss), H(ee)]
    Pq = pimi.quantize((Ic['J'] + Ic['J'].transpose(1, 2)) / 2, Ic['h0'] / 2, Ic['xq'])
    beta, gamma = pimi.SCHED['A' if s['M'] == 16 else 'B']
    ss, ee = kp.pimi(Pq, 128, 12, 987654321 + K, mode='chains', beta=beta, gamma=gamma)
    out['cases']['pimi_%s_K%d' % (shape, K)] = [H(ss), H(ee)]
json.dump(out, open(sys.argv[1], 'w'), indent=1)
print(json.dumps(out, indent=1))
