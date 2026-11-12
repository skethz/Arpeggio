#!/usr/bin/env python3
"""Tests of the PIMI CUDA kernel (pimi_kernel.cu) against its bit-exact PyTorch definition pimi.pimi_fx (milestone D),
written before the kernel and run first against the stub (RED), then against the kernel (GREEN).
1. The device Philox4x32-10 equals Random123's known-answer vectors (the host one is anefx's, checked in milestone B).
2. Kernel == pimi_fx bit for bit: per-trial final spins and energies (mode 'chains') and the selected trial (mode
   'best', which must also equal pimi.select of the reference), on DI-MIMO problems from the authors' channel model
   and ours: 8x8 16-QAM (32 spins), 8x8 64-QAM (32), 16x16 QPSK and 16-QAM (64), 32x32 QPSK and 16-QAM (128), the
   theoretical-optimal step count, 40 trials (more than the warps), a 64-bit seed and an instance offset, and two
   corner cases: zero noise (eta = 0, which makes spins 0 through np.sign's zero) and saturated fields (J and h scaled
   up to the 16-bit limits), and schedule B (beta 1, the QPSK schedule).
Usage: test_pimi_kernel.py CUBIN. Exit status 0 only if every check passes."""
import sys

import torch

import anefx
import mimo
import pimi

torch.backends.cuda.matmul.allow_tf32 = False
ok = True


def check(name, cond, msg=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + (': ' + msg if msg else ''), flush=True)
    ok = ok and bool(cond)


kern = pimi.PimiKernel(sys.argv[1])
words = torch.tensor([list(c) + list(k) for c, k, _ in anefx.KAT], dtype=torch.int64)
dev = kern.philox_kat(words)
want = torch.tensor([list(w) for _, _, w in anefx.KAT], dtype=torch.int64)
check('device Philox KAT', torch.equal(dev.cpu(), want), str(dev.cpu().tolist()))


def prob(Nt, M, x, B, gen='pimi', seed=5, jscale=1.0):
    g = torch.Generator(device='cuda'); g.manual_seed(seed)
    if gen == 'pimi':
        b = pimi.make_batch_pimi(B, Nt, Nt, M, x, g)
    else:
        b = mimo.make_batch(B, Nt, Nt, M, x, g)
    P = pimi.problem(b, pimi.slice_levels(pimi.mmse_z(b), M))
    if jscale != 1.0:                                                     # saturation corner case
        P = dict(P, Jq=torch.clamp(P['Jq'] * int(jscale), pimi.QMIN, pimi.QMAX),
                 hq=torch.clamp(P['hq'] * int(jscale), pimi.QMIN, pimi.QMAX))
    return P


cases = [  # name, problem args, steps, trials, seed, inst0, gamma, warps
    ('8x8 16-QAM, 32 steps', (8, 16, 20.0, 24), 32, 32, 11, 0, pimi.GAMMA, 8),
    ('8x8 64-QAM, 64 steps', (8, 64, 30.0, 16), 64, 32, 12, 0, pimi.GAMMA, 8),
    ('16x16 QPSK, 32 steps', (16, 4, 10.0, 16), 32, 32, 13, 0, pimi.GAMMA, 8),
    ('16x16 16-QAM, 64 steps', (16, 16, 25.0, 16), 64, 32, 14, 0, pimi.GAMMA, 8),
    ('16x16 16-QAM, 256 steps, our channel', (16, 16, 26.0, 8, 'ours'), 256, 32, 15, 3, pimi.GAMMA, 16),
    ('32x32 QPSK, 64 steps', (32, 4, 11.0, 6), 64, 32, 16, 0, pimi.GAMMA, 8),
    ('32x32 16-QAM, 128 steps', (32, 16, 22.0, 4, 'ours'), 128, 32, 17, 0, pimi.GAMMA, 32),
    ('16x16 16-QAM, 40 trials, 64-bit seed, offset', (16, 16, 15.0, 6), 64, 40, 2 ** 40 + 3, 123456, pimi.GAMMA, 8),
    ('16x16 16-QAM, zero noise (spins 0)', (16, 16, 20.0, 8), 16, 32, 18, 0, (1e9, 1e9), 8),
    ('16x16 16-QAM, saturated fields', (16, 16, 20.0, 8, 'pimi', 5, 9.0), 32, 32, 19, 0, pimi.GAMMA, 8),
    ('16x16 QPSK, schedule B (beta 1)', (16, 4, 8.0, 16), 32, 32, 20, 0, pimi.SCHED['B'][1], 8, pimi.SCHED['B'][0]),
    ('32x32 QPSK, schedule B, 256 steps', (32, 4, 11.0, 4, 'ours'), 256, 32, 21, 7, pimi.SCHED['B'][1], 8, pimi.SCHED['B'][0]),
]
for case in cases:
    name, pa, steps, R, seed, inst0, gamma, warps = case[:8]
    beta = case[8] if len(case) > 8 else pimi.BETA
    P = prob(*pa)
    rs, re = pimi.pimi_fx(P, steps, R, seed, inst0=inst0, gamma=gamma, beta=beta)
    ks, ke = kern.pimi(P, steps, R, seed, inst0=inst0, mode='chains', warps=warps, gamma=gamma, beta=beta)
    torch.cuda.synchronize()
    same_s = torch.equal(rs.to(torch.int8), ks)
    same_e = torch.equal(re, ke.to(torch.int64))
    nz = int((rs == 0).sum())
    nd = int((rs.to(torch.int8) != ks).any(-1).sum())
    check(name + ' (per trial)', same_s and same_e, 'states %s, energies %s, %d of %d trials differ, %d zero spins' %
          ('equal' if same_s else 'DIFFER', 'equal' if same_e else 'DIFFER', nd, re.numel(), nz))
    sb = pimi.select(P, rs, re)
    eb = re.min(1).values
    kbs, kbe = kern.pimi(P, steps, R, seed, inst0=inst0, mode='best', warps=warps, gamma=gamma, beta=beta)
    torch.cuda.synchronize()
    check(name + ' (best)', torch.equal(sb.to(torch.int8), kbs) and torch.equal(eb, kbe.to(torch.int64)))
sys.exit(0 if ok else 1)
