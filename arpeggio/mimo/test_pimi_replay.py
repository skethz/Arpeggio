#!/usr/bin/env python3
"""Reproduction gate (milestone D): our PIMI (pimi.pimi_inject, the arithmetic shared by pimi_torch, pimi_fx and the
kernel) against the authors' own code, src/pbits_im.py run unmodified (class pbits_Ising_Machine, mode 'fixed',
16 bits with 12 fractional, algorithm 'tanh_lut', parallel; both of their schedules, A and B, see pimi.py), on the
authors' own DI-MIMO instances from their Zenodo archives, with the same N(0, 1) samples and start states fed to both.
Checks per instance: every trial's final state, every trial's final energy (theirs x 2^13 == our 2E), the selected
trial, and the decided symbols' bits (their eval_ber logic: x_mmse + T s, nearest constellation point).
Run with python -I. Usage: test_pimi_replay.py ZIPDIR THEIR_SRC_DIR [n per case]. Exit 0 only if all match."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'pimi_stubs'), os.path.abspath(sys.argv[2])]

import numpy as np  # noqa: E402
import torch  # noqa: E402

import pimi  # noqa: E402
import pimi_zen  # noqa: E402
from pbits_im import pbits_Ising_Machine  # noqa: E402  (the authors' module, read before use)

zipdir = sys.argv[1]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
ok = True
cases = [(16, 16, 20, 64), (16, 16, 30, 64), (16, 16, 25, 256), (8, 16, 25, 32), (16, 4, 10, 32), (8, 4, 12, 16),
         (8, 64, 30, 64), (16, 64, 35, 64)]
for (nt, M, snr, steps), sname in [(c, s) for c in cases for s in ('A', 'B')]:
    beta, gamma = pimi.SCHED[sname]
    J, h, xt, xm, _ = pimi_zen.load(zipdir, nt, M, snr, list(range(n)), (), procs=1)
    N = J.shape[1]
    R = 32
    betas = np.ones(steps) * beta
    etas = np.sqrt(1 / (5 * (np.linspace(gamma[0], gamma[1], steps))))
    rng = np.random.default_rng(1000 * nt + 10 * M + snr)
    nbad = dict(states=0, energies=0, selected=0, bits=0)
    for k in range(n):
        noise = rng.standard_normal((steps, N, R))
        init = rng.choice([-1, 1], size=(N, R)).astype(np.float64)
        PIM = pbits_Ising_Machine(J[k], h[k], 'fixed', 16, 12)
        PIM.pbar = False
        PIM.tanh_levels = 4
        PIM.run_simulation(steps, R, betas, etas, True, 'tanh_lut', pbits_init=init.copy(), random_values=noise)
        fin = PIM.result['final_states']                                    # (N, R)
        E = PIM.estimate_energy_for_all()                                   # (R,)
        sel_their = int(E.argmin())
        P = pimi.quantize(torch.tensor(J[k:k + 1]), torch.tensor(h[k:k + 1]), torch.tensor(xm[k:k + 1], dtype=torch.float32))
        S, E2 = pimi.pimi_inject(P, steps, torch.tensor(noise.transpose(0, 2, 1)[:, None]), torch.tensor(init.T[None]),
                                 beta=beta, gamma=gamma)
        same_s = np.array_equal(S[0].numpy().T, fin)
        same_e = np.array_equal(E2[0].numpy(), np.round(E * 8192).astype(np.int64)) and np.allclose(E * 8192, np.round(E * 8192))
        sel_our = int(E2[0].argmin())                                     # first minimum, as np.argmin
        # decisions: theirs (eval_ber: d = T s, u = d + x_mmse, nearest point) and ours
        s_t = fin[:, sel_their]
        D = 2 * nt
        u = xm[k] + s_t[:D] + s_t[D:]
        l_their = pimi.slice_levels(torch.tensor(u, dtype=torch.float32)[None], M)
        l_our = pimi.decide(P, pimi.select(P, S, E2), M)
        same_b = torch.equal(pimi.to_bits(l_their, M), pimi.to_bits(l_our, M))
        nbad['states'] += not same_s; nbad['energies'] += not same_e
        nbad['selected'] += sel_their != sel_our; nbad['bits'] += not same_b
    good = all(v == 0 for v in nbad.values())
    ok = ok and good
    print(('PASS' if good else 'FAIL') + ' schedule %s, %dx%d %d-QAM Eb/N0 %d dB, %d steps, %d instances x %d trials (%d spins): '
          'mismatching states %d, energies %d, selected trial %d, bits %d' %
          (sname, nt, nt, M, snr, steps, n, R, N, nbad['states'], nbad['energies'], nbad['selected'], nbad['bits']), flush=True)
sys.exit(0 if ok else 1)
