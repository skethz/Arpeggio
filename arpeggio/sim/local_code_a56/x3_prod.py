#!/usr/bin/env python3
"""A5.6 X3 (PROTOCOL_A56.md section 4): the production engine model, fx_xs mode of antiphase_asic's workload.py, on the runner's draws, CPU only, on
the runner's host-independent draws. Same arithmetic as workload.py: anefx.to_fixed, antiphase_ref.compress, ape_py.solve_batch, the
logged MDI wrapper. Writes ROOT/X3P/<shape>/prod_fx_xs_<Ns>/snr_<snr>/bNNNNN.npz with batches resumable; done.json at the stop rule.
Usage: x3_prod.py ROOT --nt 32 --M 16 --snr 22 --ns 8 --seed 102 --B 1000 --min-vec 2000 --max-uses 300000 [--tag x32]
       x3_prod.py --check OUT.json        reproduces workload.py on make_batch draws: seed 42, P2, 2,000 uses, prints bit errors and cycles"""
import argparse
import json
import math
import os
import sys
import time

MD = '<SCRATCH>/ap_ber_20261024/x3model'
sys.path.insert(0, MD)
import numpy as np
import torch

import antiphase_ref as ar
import anefx
import ape_py
import mdi_solvers
import mimo

ap = argparse.ArgumentParser()
ap.add_argument('root', nargs='?')
ap.add_argument('--nt', type=int); ap.add_argument('--M', type=int); ap.add_argument('--snr', type=float); ap.add_argument('--ns', type=int)
ap.add_argument('--seed', type=int); ap.add_argument('--B', type=int); ap.add_argument('--min-vec', type=int, default=100); ap.add_argument('--max-uses', type=int, default=156250)
ap.add_argument('--tag', default=None); ap.add_argument('--check', default=None); ap.add_argument('--threads', type=int, default=4)
a = ap.parse_args()
MDIANE = mdi_solvers.MDIANE
TF = '<SCRATCH>/ap_ber_20261024/logs/a56/x3_threads'


def nth():
    try:
        return max(1, min(16, int(open(TF).read())))
    except Exception:
        return a.threads


@torch.no_grad()
def mdi_logged(b, solver, Ns, Rmax, S, guesses, heuristic='mean', sic_per='real', na_round='ceil'):
    """workload.py's mdi_logged."""
    M = b['M']
    B = b['H'].shape[0]
    dev = b['H'].device
    z_mmse, Ai, _ = mimo.mmse(b)
    cur = {g: (mimo.quantize_levels(z_mmse / mimo._mu(b, z_mmse), M) if g == 'mmse' else mimo.mmse_sic(b, per=sic_per)) for g in guesses}
    ann = torch.zeros(B, device=dev)
    for st in range(S):
        R = {g: mimo.mdi_radius(b, cur[g], Rmax, heuristic)[0] for g in guesses}
        tot = sum(R[g] for g in guesses)
        if int(tot.max()) == 0:
            break
        nxt = {}
        for g in guesses:
            bl, bd = cur[g].clone(), mimo.dist(b, cur[g][:, None, :])[:, 0]
            for K in range(1, Rmax + 1):
                need = R[g] >= K
                if not bool(need.any()):
                    continue
                for t in torch.unique(tot[need]).tolist():
                    idx = torch.nonzero(need & (tot == t)).flatten()
                    na = math.ceil(Ns / t) if na_round == 'ceil' else max(1, Ns // t)
                    sb = mimo.subset(b, idx)
                    I = mimo.ising_delta_at(sb, cur[g][idx], K)
                    Ssp = solver(I, na, K, dict(idx=idx, stage=st, guess=g))
                    Lc = mimo.spins_to_levels_delta(Ssp, I, M)
                    dd = mimo.dist(sb, Lc)
                    dm, im = dd.min(1)
                    better = dm < bd[idx]
                    bd[idx] = torch.where(better, dm, bd[idx])
                    bl[idx] = torch.where(better[:, None], Lc[torch.arange(len(idx), device=dev), im], bl[idx])
                    ann[idx] += na
            nxt[g] = bl
        cur = nxt
    allc = torch.stack([cur[g] for g in guesses], 1)
    d = mimo.dist(b, allc)
    return allc[torch.arange(B, device=dev), d.argmin(1)], ann


dummy = dict(J=torch.zeros(1, 2, 2), h=torch.zeros(1, 2), h0=torch.zeros(1, 2))
TAB = {}
for K in (1, 2, 3):
    F = anefx.to_fixed(dummy, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
    TAB[K] = (F['T'].numpy().astype(np.int16), F['c'].numpy().astype(np.int16), int(F['q']))


def detect(b, nt, M, ns, seed):
    """One batch through the engine model, as workload.py with --solver fx_xs. Returns x_hat, cycles per use, anneals per use, per-K flips and decisions."""
    cfg = mdi_solvers.MDI[('%dx%d' % (nt, nt), M)]
    B = b['H'].shape[0]
    seed_base = (seed * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    calls = [0]
    cyc_u = np.zeros(B, dtype=np.int64)
    cnt = {}

    def solver(I, na, K, meta):
        ci = calls[0]; calls[0] += 1
        F = anefx.to_fixed(I, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
        G, h = ar.compress(F, K)
        T, c, q = TAB[K]
        idx = meta['idx'].numpy()
        spins, de, cyc, st = ape_py.solve_batch(G.numpy(), h.numpy(), 2 * K, na, T, c, q, idx.astype(np.uint32),
                                                (seed_base + ci * 0xD1B54A32D192ED03) & 0xFFFFFFFFFFFFFFFF, A=4, philox=0, nthreads=nth())
        np.add.at(cyc_u, idx, cyc)
        v = cnt.setdefault(str(K), [0, 0, 0])
        v[0] += int(st[:, 0].sum()); v[1] += int(st[:, 1].sum()); v[2] += int(na * len(idx))
        return torch.from_numpy(spins).float()
    lh, ann = mdi_logged(b, solver, ns, cfg['Rmax'], cfg['S'], tuple(cfg['guesses']))
    return lh, cyc_u, ann.numpy(), cnt


if a.check:
    torch.set_num_threads(8)
    gen = torch.Generator(device='cpu').manual_seed(42)
    b = mimo.make_batch(2000, 32, 32, 16, 22.0, gen, device='cpu')
    lh, cyc, ann, cnt = detect(b, 32, 16, 8, 42)
    err, nb = mimo.bit_errors(b, lh)
    r = dict(bit_errors=int(err), bits=int(nb), standalone_cycles_per_det=float(cyc.mean()), anneals_per_det=float(ann.mean()), cnt=cnt)
    json.dump(r, open(a.check, 'w'))
    print(json.dumps(r))
    sys.exit()

import apx  # noqa: E402

tag = a.tag or ('x%d' % a.nt)
d = os.path.join(a.root, 'X3P', tag, 'prod_fx_xs_%d' % a.ns, 'snr_%05.2f' % a.snr)
os.makedirs(d, exist_ok=True)
bpu = 2 * a.nt * (1 if a.M == 4 else 2)
files = sorted(f for f in os.listdir(d) if f.startswith('b') and f.endswith('.npz'))
nb = len(files); n = ve = be = 0
for f in files:
    x = np.load(os.path.join(d, f), allow_pickle=False)['biterr']
    n += len(x); ve += int((x > 0).sum()); be += int(x.sum())
while ve < a.min_vec and n < a.max_uses:
    bi = nb
    torch.set_num_threads(nth())
    m = min(a.B, a.max_uses - n)
    bg = apx.draw(a.seed, a.snr, bi, a.B, a.nt, a.M, dev='cpu')            # the runner's draw (CPU generator, host-independent)
    b = dict(bg)
    for k in ('H', 'y', 'l'):
        b[k] = bg[k][:m].contiguous().cpu()
    del bg
    t0 = time.time()
    lh, cyc, ann, cnt = detect(b, a.nt, a.M, a.ns, apx.draw_seed(a.seed, a.snr, bi))
    bev = apx.biterr_per_use(b, lh)
    err = torch.nonzero(bev > 0).flatten()
    info = dict(cnt=cnt, wall_untimed=time.time() - t0, threads=nth(), bi=bi, m=m, N0=b['N0'])
    tmp = os.path.join(d, '.tmp_b%05d.npz' % bi)
    np.savez_compressed(tmp, biterr=bev.numpy().astype(np.uint8), err_idx=err.numpy().astype(np.int32), xhat=lh[err].numpy().astype(np.int8), cycles=cyc, anneals=ann.astype(np.float32), info=np.array(json.dumps(info)))
    os.rename(tmp, os.path.join(d, 'b%05d.npz' % bi))
    nb += 1; n += m; ve += int((bev > 0).sum()); be += int(bev.sum())
    print(time.strftime('%m-%d %H:%M:%S'), tag, 'batch', bi, 'uses', n, 'err uses', ve, 'bit err', be, '%.1f s' % info['wall_untimed'], flush=True)
json.dump(dict(uses=n, vec_err=ve, bit_err=be, ber=be / (n * bpu), batches=nb, seed=a.seed, snr=a.snr, capped=n >= a.max_uses, t=time.time()), open(os.path.join(d, 'done.json'), 'w'))
print('DONE', tag, flush=True)
