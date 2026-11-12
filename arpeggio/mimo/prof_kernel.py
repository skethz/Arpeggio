#!/usr/bin/env python3
"""Development timing of the kernel pipeline stages (shared GPU6; not the cohort): MMSE, Ising mapping, fixed point,
kernel, selection, for 16x16 QPSK RI and 16x16 16-QAM dDI."""
import sys
import time

import torch

import anefx
import fxdetect
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
kern = anefx.Kernel(sys.argv[1])
B = int(sys.argv[2]) if len(sys.argv) > 2 else 100000


def tm(f, rep=3):
    f(); torch.cuda.synchronize()
    t = time.time()
    for _ in range(rep):
        out = f()
    torch.cuda.synchronize()
    return (time.time() - t) / rep, out


for name in ('q16', 'x16'):
    sc = fxdetect.SCHED[name]
    g = torch.Generator(device='cuda'); g.manual_seed(5)
    b = mimo.make_batch(B, sc['Nt'], sc['Nr'], sc['M'], 12.0 if name == 'q16' else 22.0, g)
    t_mmse, (z, Ai, _) = tm(lambda: mimo.mmse(b))
    lm = mimo.mmse_hard(b, z, Ai)
    if sc['kind'] == 'ri':
        t_map, I = tm(lambda: mimo.ising(b, z)); P = 1
    else:
        t_map, I = tm(lambda: mimo.ising_delta_at(b, lm, 1)); P = 2
    t_fx, F = tm(lambda: anefx.to_fixed(I, sc['S'], sc['t0'], sc['t1'], sc['q'], sc['kappa']))
    for R in (1, 4, 16, 64):
        mode = 'best' if sc['kind'] == 'ri' else 'chains'
        t_k, (s8, e) = tm(lambda: kern.anechoic(F, R, 9, P=P, mode=mode))
        s = s8.float()[:, None, :] if mode == 'best' else s8.float()
        D = b['H'].shape[-1]
        L = (lambda: mimo.spins_to_levels(s, b['M'], D)) if sc['kind'] == 'ri' else (lambda: mimo.spins_to_levels_delta(s, I, b['M']))
        t_sel, _ = tm(lambda: mimo.select(b, L(), lm))
        tot = t_mmse + t_map + t_fx + t_k + t_sel
        print('%s R%-3d per-stage us/det: mmse %.3f map %.3f fixed %.3f kernel %.3f select %.3f | kernel %.2fM det/s, pipeline %.2fM det/s'
              % (name, R, 1e6 * t_mmse / B, 1e6 * t_map / B, 1e6 * t_fx / B, 1e6 * t_k / B, 1e6 * t_sel / B, B / t_k / 1e6, B / tot / 1e6), flush=True)
