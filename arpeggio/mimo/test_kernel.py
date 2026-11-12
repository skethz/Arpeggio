#!/usr/bin/env python3
"""Tests of the custom Anechoic kernel against the PyTorch reference (DESIGN.md B3). Usage: test_kernel.py CUBIN.
1. Philox4x32-10 on the host (PyTorch) equals Random123's known-answer vectors.
2. The device Philox equals them too.
3. Kernel == anechoic_fx bit for bit (per-anneal best spins and energies; and mode 'best') on problems from the real
   MIMO mappings: 16x16 QPSK RI (32 spins), 16x16 16-QAM dDI K=1 (64, 2 phases), 32x32 16-QAM dDI K=1 with
   kappa 0.3 (128), 16x16 16-QAM dDI K=3 (192, 6 phases), 64x64 16-QAM dDI K=1 (256), 40 anneals (more than the
   warps), a non-zero instance offset and a 64-bit seed.
Exit status 0 only if every check passes."""
import sys

import torch

import anefx
import mimo

torch.backends.cuda.matmul.allow_tf32 = False
ok = True


def check(name, cond, msg=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + (': ' + msg if msg else ''), flush=True)
    ok = ok and bool(cond)


# 1
host = []
for ctr, key, want in anefx.KAT:
    t = [torch.tensor([v], dtype=torch.int64) for v in ctr]
    got = tuple(int(x) for x in anefx.philox(*t, key[0], key[1]))
    host.append(got == want)
check('host Philox KAT', all(host), str(host))
# 2
kern = anefx.Kernel(sys.argv[1])
words = torch.tensor([list(c) + list(k) for c, k, _ in anefx.KAT], dtype=torch.int64)
dev = kern.philox_kat(words)
want = torch.tensor([list(w) for _, _, w in anefx.KAT], dtype=torch.int64)
check('device Philox KAT', torch.equal(dev.cpu(), want), str(dev.cpu().tolist()))


# 3
def problem(Nt, M, snr, B, kind, K=1, seed=5):
    g = torch.Generator(device='cuda'); g.manual_seed(seed)
    b = mimo.make_batch(B, Nt, Nt, M, snr, g)
    z, Ai, _ = mimo.mmse(b)
    if kind == 'ri':
        return mimo.ising(b, z)
    return mimo.ising_delta_at(b, mimo.mmse_hard(b, z, Ai), K)


cases = [  # name, problem args, R, S, t0, t1, q, kappa, P, seed, inst0
    ('16x16 QPSK RI', (16, 4, 10.0, 64, 'ri'), 16, 128, 0.7, 0.5, 0.6, 0.0, 1, 7, 0),
    ('16x16 QPSK RI kappa', (16, 4, 10.0, 64, 'ri'), 16, 128, 2.0, 0.05, 0.5, 0.3, 1, 8, 1000),
    ('16x16 16-QAM dDI K1', (16, 16, 20.0, 64, 'ddi', 1), 16, 256, 0.3, 0.3, 0.4, 0.0, 2, 9, 0),
    ('32x32 16-QAM dDI K1 kappa', (32, 16, 22.0, 32, 'ddi', 1), 8, 128, 0.3, 0.2, 0.4, 0.3, 2, 10, 77),
    ('16x16 16-QAM dDI K3', (16, 16, 18.0, 24, 'ddi', 3), 4, 96, 0.3, 0.3, 0.4, 0.0, 6, 11, 5),
    ('64x64 16-QAM dDI K1', (64, 16, 24.0, 8, 'ddi', 1), 3, 32, 0.3, 0.3, 0.4, 0.0, 2, 12, 0),
    ('16x16 QPSK RI 40 anneals', (16, 4, 12.0, 16, 'ri'), 40, 64, 0.7, 0.5, 0.6, 0.0, 1, 2 ** 40 + 3, 123456),
]
for name, pa, R, S, t0, t1, q, kappa, P, seed, inst0 in cases:
    I = problem(*pa)
    F = anefx.to_fixed(I, S, t0, t1, q, kappa)
    rs, re = anefx.anechoic_fx(F, R, seed, P=P, inst0=inst0)
    ks, ke = kern.anechoic(F, R, seed, P=P, inst0=inst0)
    torch.cuda.synchronize()
    same_e = torch.equal(re, ke)
    same_s = torch.equal(rs, ks)
    nd = int((rs != ks).any(-1).sum())
    check(name + ' (per anneal)', same_e and same_s, 'energies %s, states %s, %d of %d anneals differ' %
          ('equal' if same_e else 'DIFFER', 'equal' if same_s else 'DIFFER', nd, re.numel()))
    rbs, rbe = anefx.anechoic_fx(F, R, seed, P=P, inst0=inst0, mode='best')
    kbs, kbe = kern.anechoic(F, R, seed, P=P, inst0=inst0, mode='best')
    torch.cuda.synchronize()
    check(name + ' (best)', torch.equal(rbs, kbs) and torch.equal(rbe, kbe))
sys.exit(0 if ok else 1)
