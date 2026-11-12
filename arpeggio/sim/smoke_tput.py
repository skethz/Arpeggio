#!/usr/bin/env python3
"""Development throughput smoke test on GPU7 (dev seed 9001; not held-out data, not a timing claim)."""
import json, os, sys, time, math
import numpy as np, torch
import mimo, anefx, ahcfx, tree, mdi_solvers as ms
torch.backends.cuda.matmul.allow_tf32 = False
ka = anefx.Kernel(os.environ['ANE_CUBIN']); kh = ahcfx.AhcKernel(os.environ['AHC_CUBIN'])
which = sys.argv[1].split(',')
def run(tag, nt, M, snr, n, Ns, impl, shape):
    g = torch.Generator(device='cuda'); g.manual_seed(9001)
    b = mimo.make_batch(n, nt, nt, M, snr, g)
    gs = torch.Generator(device='cuda'); gs.manual_seed(9002)
    cfg = ms.MDI[(shape, M)]
    solver = ms.Timed(ms.make_solver(impl, gs, ka, kh, seed0=55))
    torch.cuda.synchronize(); t0 = time.time()
    lh, st = ms.detect(b, impl, Ns, cfg, solver)
    torch.cuda.synchronize(); dt = time.time() - t0
    e, nb = mimo.bit_errors(b, lh)
    print(json.dumps(dict(tag=tag, impl=impl, n=n, Ns=Ns, snr=snr, sec=round(dt, 2), det_s=round(n / dt, 1), solver_s=round(solver.t, 2), ber=e / nb, anneals=st['anneals'] / n)), flush=True)
for w in which:
    if w == 'x16':
        for impl in ('ane_kernel', 'ahc_kernel', 'ane_torch', 'ahc_torch'):
            run('x16', 16, 16, 20.0, 2000, 64, impl, '16x16')
    if w == 'x16ns8':
        for impl in ('ane_kernel', 'ahc_kernel'):
            run('x16ns8', 16, 16, 22.0, 2000, 8, impl, '16x16')
    if w == 'x32':
        for impl in ('ane_torch', 'ahc_torch'):
            run('x32', 32, 16, 22.0, 1000, 128, impl, '32x32')
    if w == 'q32':
        for impl in ('ane_kernel', 'ahc_kernel', 'ane_torch', 'ahc_torch'):
            run('q32', 32, 4, 12.0, 4000, 64, impl, '32x32')
    if w == 'q16':
        ms.MDI[('16x16', 4)] = ms.MDI[('32x32', 4)]
        for impl in ('ane_kernel', 'ahc_kernel'):
            run('q16', 16, 4, 12.0, 4000, 64, impl, '16x16')
    if w in ('kb16', 'kb32', 'sd16', 'sd16q'):
        nt, M, snr, n = {'kb16': (16, 16, 20.0, 4000), 'kb32': (32, 16, 22.0, 2000), 'sd16': (16, 16, 18.0, 2000), 'sd16q': (16, 4, 9.0, 4000)}[w]
        g = torch.Generator(device='cuda'); g.manual_seed(9001)
        b = mimo.make_batch(n, nt, nt, M, snr, g)
        Hn, yn = b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy()
        lv = np.array(mimo.PAM[M]['levels'], np.float64)
        for rep in range(2):
            t0 = time.time()
            if w.startswith('kb'):
                out, _ = tree.kbest2(Hn, yn, lv, 32); extra = {}
            else:
                out, nodes, done = tree.sphere_decoder(Hn, yn, lv, 2_000_000); extra = dict(nodes_mean=float(nodes.mean()), nodes_max=int(nodes.max()), unfinished=int((~done).sum()))
            dt = time.time() - t0
        e, nb = mimo.bit_errors(b, torch.tensor(out, device='cuda', dtype=torch.float32))
        print(json.dumps(dict(tag=w, n=n, sec=round(dt, 2), det_s=round(n / dt, 1), ber=e / nb, **extra)), flush=True)
