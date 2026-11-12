#!/usr/bin/env python3
"""Unit checks for milestone B's MDI-MIMO pieces (DESIGN.md B1). Prints one line per check and exits non-zero on failure.
1. dDI around any guess, K = 1..3: scale * E0(s) + c equals ||y - H (xg + T s)||^2 for random spins (unclipped).
2. Radius rule with lambda_min: R = 0 implies the guess is ML (exhaustive search, 3x3 16-QAM).
3. MMSE-SIC (both orderings) beats MMSE at 16x16 16-QAM, 20 dB (tuning seed).
4. MDI with a strong solver (Anechoic-dDI, many anneals) finds ML on 3x3 16-QAM in nearly every instance."""
import itertools
import math
import sys

import torch

import mimo

torch.backends.cuda.matmul.allow_tf32 = False
ok = True


def check(name, cond, msg):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + ': ' + msg, flush=True)
    ok = ok and bool(cond)


g = torch.Generator(device='cuda'); g.manual_seed(1000)
# 1
b = mimo.make_batch(64, 8, 8, 16, 18.0, g)
z, Ai, _ = mimo.mmse(b)
xg = mimo.mmse_hard(b, z, Ai)
worst = 0.0
for K in (1, 2, 3):
    I = mimo.ising_delta_at(b, xg, K)
    s = torch.where(torch.rand(64, 20, I['h'].shape[1], generator=g, device='cuda') < 0.5, -1.0, 1.0)
    d = (s.reshape(64, 20, 2 * K, -1)).sum(-2)
    true = mimo.dist(b, xg[:, None, :] + d)
    e = I['scale'][:, None] * mimo.energy0(s, I['h0'], I['J'])
    c = true - e
    worst = max(worst, float(((c - c[:, :1]).abs() / true.abs().amax(1, keepdim=True)).max()))
check('dDI energy = distance', worst < 1e-4, 'max relative deviation %.2e (K = 1..3)' % worst)
# 2
Nt, M = 3, 16
lv = torch.tensor(mimo.PAM[M]['levels'], device='cuda', dtype=torch.float32)
allx = torch.tensor(list(itertools.product(mimo.PAM[M]['levels'], repeat=2 * Nt)), device='cuda', dtype=torch.float32)
nbad = nzero = 0
for snr in (10.0, 16.0, 22.0):
    b = mimo.make_batch(400, Nt, Nt, M, snr, g)
    z, Ai, _ = mimo.mmse(b)
    xg = mimo.mmse_hard(b, z, Ai)
    R, Gam = mimo.mdi_radius(b, xg, 3, 'min')
    dall = torch.cat([mimo.dist(b[None] if False else mimo.subset(b, torch.arange(i, min(i + 100, 400), device='cuda')),
                                allx[None].expand(min(100, 400 - i), -1, -1)) for i in range(0, 400, 100)])
    ml = allx[dall.argmin(1)]
    zero = R == 0
    nzero += int(zero.sum())
    nbad += int(((ml != xg).any(1) & zero).sum())
check('radius rule (lambda_min)', nbad == 0, '%d of %d instances with R = 0 are not ML' % (nbad, nzero))
# 3
b = mimo.make_batch(2000, 16, 16, 16, 20.0, g)
z, Ai, _ = mimo.mmse(b)
lm = mimo.mmse_hard(b, z, Ai)
be = {}
for name, lh in (('mmse', lm), ('sic_real', mimo.mmse_sic(b, 'real')), ('sic_complex', mimo.mmse_sic(b, 'complex'))):
    e, n = mimo.bit_errors(b, lh); be[name] = e / n
check('MMSE-SIC beats MMSE', be['sic_real'] < be['mmse'] and be['sic_complex'] < be['mmse'],
      ' '.join('%s %.3e' % kv for kv in be.items()))
# 4
gs = torch.Generator(device='cuda'); gs.manual_seed(1000 + 7919)


def solver(I, na, K):
    return mimo.anechoic(I, na, 128 * 2 * K, 0.3, 0.3, 0.4, gen=gs, phases=2 * K)


hit = tot = 0
for snr in (12.0, 18.0):
    b = mimo.make_batch(400, Nt, Nt, M, snr, g)
    lh = mimo.mdi(b, solver, 64, 3, 8)
    dall = torch.cat([mimo.dist(mimo.subset(b, torch.arange(i, i + 100, device='cuda')), allx[None].expand(100, -1, -1))
                      for i in range(0, 400, 100)])
    ml = allx[dall.argmin(1)]
    hit += int((lh == ml).all(1).sum()); tot += 400
check('MDI(Anechoic) finds ML', hit >= 0.97 * tot, '%d of %d instances' % (hit, tot))
sys.exit(0 if ok else 1)
