#!/usr/bin/env python3
"""Tests of the AHC-CIM kernel (ahc_kernel.cu) against the order-defined PyTorch reference ahcfx.ahc_od (milestone C):
per-anneal best spins and energies bit-identical on problems from the real mappings — 16x16 QPSK RI (32 spins, h != h0),
16x16 16-QAM dDI K = 1, 2, 3 (64, 128, 192 spins), 32x32 QPSK DI (128 spins) with more anneals than warps.
Usage: test_ahc_kernel.py CUBIN. Exit status 0 only if every check passes."""
import sys

import torch

import ahcfx
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
ok = True
kern = ahcfx.AhcKernel(sys.argv[1])


def problem(Nt, M, snr, B, kind, K=1, seed=5):
    g = torch.Generator(device='cuda'); g.manual_seed(seed)
    b = mimo.make_batch(B, Nt, Nt, M, snr, g)
    z, Ai, _ = mimo.mmse(b)
    if kind == 'ri':
        return mimo.ising(b, z)
    return mimo.ising_delta_at(b, mimo.mmse_hard(b, z, Ai), K)


cases = [('16x16 QPSK RI (h != h0)', (16, 4, 10.0, 8, 'ri'), 4),
         ('16x16 16-QAM dDI K1', (16, 16, 20.0, 6, 'ddi', 1), 3),
         ('16x16 16-QAM dDI K2', (16, 16, 18.0, 4, 'ddi', 2), 2),
         ('16x16 16-QAM dDI K3', (16, 16, 18.0, 3, 'ddi', 3), 2),
         ('32x32 QPSK DI, 9 anneals', (32, 4, 12.0, 3, 'ddi', 1), 9)]
for name, pa, R in cases:
    I = problem(*pa)
    B, N = I['h0'].shape
    gs = torch.Generator(device='cuda'); gs.manual_seed(77)
    x0, e0 = ahcfx.start_state(B, R, N + 1, gs, 'cuda')
    rs, re = ahcfx.ahc_od(I, x0, e0)
    ks, ke = kern.ahc(I, x0, e0)
    torch.cuda.synchronize()
    same_s = torch.equal(rs.to(torch.int8), ks)
    same_e = torch.equal(re, ke)
    nd = int((rs.to(torch.int8) != ks).any(-1).sum())
    print(('PASS ' if same_s and same_e else 'FAIL ') + name + ': states %s, energies %s, %d of %d anneals differ' %
          ('equal' if same_s else 'DIFFER', 'equal' if same_e else 'DIFFER', nd, B * R), flush=True)
    ok = ok and same_s and same_e
sys.exit(0 if ok else 1)
