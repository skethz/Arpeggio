#!/usr/bin/env python3
"""A5.16 stage 2 (PROTOCOL_A516.md): run_a513.py (A5.13) with two options, nothing else changed. --qbits sets the fixed-point scale
Q = 2^qbits of to_fixed_q (anefx.to_fixed with J kept as int32, since Q = 2^16 overflows int16) and of fa_schedule; --key-tag sets the
first-accept stream tag (A5.13: 0xA513). At --qbits 12 --key-tag 0xA513 the output is A5.13's. Method names: fafx_* (V0), fafxq<qbits>_*,
fafxk<tag>_*.
A5.13 docstring: fixed-point first-accept SA inside the production model's MDI wrapper. This is x3_prod.py (A5.6 X3) with
the solver swapped. The draws, anefx.to_fixed and antiphase_ref.compress are as there; then fafx.solve (fa_fx.cu, bit-exact to
fa_ref59.anneal 'fa') runs on the GPU. The wrapper runs on the CPU, as for X3P.
--solver prod runs ape_py.solve_batch exactly as x3_prod.py does (gate G2: reproduce X3P's saved per-use bit errors).
Writes ROOT/<tag>/<method>/snr_<snr>/bNNNNN.npz for batch indices b0 <= bi < b1; a batch already written is skipped.
Usage: run_a513.py ROOT --tag x16 --nt 16 --M 16 --snr 20 --seed 102 --B 2000 --b0 0 --b1 14 --pick abl_far_64_0.1_0.1_0_rand_32
       [--solver fafx|prod] [--threads 6]"""
import argparse
import json
import math
import os
import sys
import time

A = '<SCRATCH>/ap_ber_20261024'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'x3model'))
sys.path.insert(0, HERE)
import numpy as np
import torch

import antiphase_ref as ar
import anefx
import apx
import mdi_solvers
import mimo

MDIANE = mdi_solvers.MDIANE
M64 = 0xFFFFFFFFFFFFFFFF
KEY_STEP = 0xD1B54A32D192ED03                      # x3_prod.py's per-call seed step
KEY_TAG = 0xA513                                   # first-accept streams differ from any production seed (A5.13; --key-tag)
QBITS = 12                                         # --qbits


def parse_pick(pick):
    """abl_far_<S>_<T0>_<T1>_<q>_<start>_<Ns> (apx55.solver_for) -> dict."""
    a = pick.split('_')
    assert a[0] == 'abl' and a[1] == 'far' and len(a) == 8, pick
    return dict(S=int(a[2]), T0=float(a[3]), T1=float(a[4]), q=float(a[5]), start=a[6], Ns=int(a[7]))


@torch.no_grad()
def mdi_logged(b, solver, Ns, Rmax, S, guesses, heuristic='mean', sic_per='real', na_round='ceil'):
    """x3_prod.py's mdi_logged (= workload.py's), unchanged."""
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


def to_fixed_q(I, S, t0, t1, q, kappa=0.0, ramp=True):
    """anefx.to_fixed at Q = 2^QBITS with J as int32 (identical values at QBITS = 12)."""
    Q = 1 << QBITS
    F = anefx.to_fixed(I, S, t0, t1, q, kappa, ramp=ramp, Q=Q) if QBITS <= 12 else None
    if F is not None:
        return F
    J = (I['J'] + I['J'].transpose(1, 2)) / 2
    F = anefx.to_fixed(dict(J=torch.zeros_like(I['J'][:, :1, :1]), h=I['h'], h0=I['h0']), S, t0, t1, q, kappa, ramp=ramp, Q=Q)
    F['J'] = torch.round(J * Q).to(torch.int32).contiguous()
    return F


def fa_schedule(pk, K):
    """Integer schedule as fa_ref59.gen: one T per pass, S sweeps x P passes; q in the same units."""
    Q = 1 << QBITS
    Tsw = [int(round(v * Q)) for v in mimo.geom(pk['T0'], pk['T1'], pk['S'], 'cpu').double().tolist()]
    return [t for t in Tsw for _ in range(2 * K)], int(round(pk['q'] * Q))


def detect(b, nt, M, seed, pk, solver_kind='fafx', threads=6, hook=None):
    """One batch. Returns x_hat, anneals per use, per-K counters [flips, tests, anneals] (fafx) or [steps, flips, anneals] (prod),
    and coefficient statistics."""
    cfg = mdi_solvers.MDI[('%dx%d' % (nt, nt), M)]
    seed_base = (seed * 0x9E3779B97F4A7C15) & M64
    calls = [0]
    cnt, cs = {}, dict(max_coef=0, over13=0, over15=0, subproblems=0)
    if solver_kind == 'prod':
        import ape_py
        TAB = {}
        dummy = dict(J=torch.zeros(1, 2, 2), h=torch.zeros(1, 2), h0=torch.zeros(1, 2))
        for K in (1, 2, 3):
            F = anefx.to_fixed(dummy, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
            TAB[K] = (F['T'].numpy().astype(np.int16), F['c'].numpy().astype(np.int16), int(F['q']))
    else:
        import fafx

    def solver(I, na, K, meta):
        ci = calls[0]; calls[0] += 1
        F = to_fixed_q(I, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
        G, h = ar.compress(F, K)
        idx = meta['idx'].numpy()
        mc = torch.maximum(G.abs().amax((1, 2)), h.abs().amax(1))
        cs['max_coef'] = max(cs['max_coef'], int(mc.max())); cs['subproblems'] += len(idx)
        cs['over13'] += int((mc >= 2 ** 13).sum()); cs['over15'] += int((mc >= 2 ** 15).sum())
        v = cnt.setdefault(str(K), [0, 0, 0])
        if solver_kind == 'prod':
            T, c, q = TAB[K]
            spins, de, cyc, st = ape_py.solve_batch(G.numpy(), h.numpy(), 2 * K, na, T, c, q, idx.astype(np.uint32),
                                                    (seed_base + ci * KEY_STEP) & M64, A=4, philox=0, nthreads=threads)
            v[0] += int(st[:, 0].sum()); v[1] += int(st[:, 1].sum()); v[2] += int(na * len(idx))
        else:
            T, qi = fa_schedule(pk, K)
            key = (seed_base + ci * KEY_STEP + KEY_TAG) & M64
            spins, de, st = fafx.solve(G, h, 2 * K, na, T, qi, idx.astype(np.int64), key, pk['start'])
            v[0] += int(st[..., 0].sum()); v[1] += int(st[..., 1].sum()); v[2] += int(na * len(idx))
            if hook is not None:
                hook(dict(G=G, h=h, P=2 * K, R=na, T=T, q=qi, inst=idx.astype(np.int64), key=key, start=pk['start'], spins=spins, de=de, st=st))
        return torch.from_numpy(spins).float()
    lh, ann = mdi_logged(b, solver, pk['Ns'], cfg['Rmax'], cfg['S'], tuple(cfg['guesses']))
    return lh, ann.numpy(), cnt, cs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--tag'); ap.add_argument('--nt', type=int); ap.add_argument('--M', type=int); ap.add_argument('--snr', type=float)
    ap.add_argument('--seed', type=int); ap.add_argument('--B', type=int); ap.add_argument('--b0', type=int); ap.add_argument('--b1', type=int)
    ap.add_argument('--pick'); ap.add_argument('--solver', default='fafx'); ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--prod-ns', type=int, default=None)
    ap.add_argument('--qbits', type=int, default=12); ap.add_argument('--key-tag', type=lambda x: int(x, 0), default=0xA513)
    a = ap.parse_args()
    global QBITS, KEY_TAG
    QBITS, KEY_TAG = a.qbits, a.key_tag
    torch.set_num_threads(a.threads)
    if a.solver == 'prod':
        pk = dict(Ns=a.prod_ns)
        method = 'prod_fx_xs_%d' % a.prod_ns
    else:
        pk = parse_pick(a.pick)
        method = a.pick.replace('abl_far_', 'fafx_' if (a.qbits, a.key_tag) == (12, 0xA513) else
                                ('fafxq%d_' % a.qbits if a.key_tag == 0xA513 else 'fafxk%x_' % a.key_tag))
    d = os.path.join(a.root, a.tag, method, 'snr_%05.2f' % a.snr)
    os.makedirs(d, exist_ok=True)
    gpu = torch.cuda.get_device_name(0) if a.solver == 'fafx' else 'cpu'
    for bi in range(a.b0, a.b1):
        fn = os.path.join(d, 'b%05d.npz' % bi)
        if os.path.exists(fn):
            continue
        b = apx.draw(a.seed, a.snr, bi, a.B, a.nt, a.M, dev='cpu')            # the runner's draw (CPU generator, host-independent)
        t0 = time.time()
        lh, ann, cnt, cs = detect(b, a.nt, a.M, apx.draw_seed(a.seed, a.snr, bi), pk, a.solver, a.threads)
        bev = apx.biterr_per_use(b, lh)
        err = torch.nonzero(bev > 0).flatten()
        info = dict(cnt=cnt, coef=cs, wall=time.time() - t0, threads=a.threads, bi=bi, m=a.B, N0=b['N0'], gpu=gpu, solver=a.solver,
                    pick=a.pick, seed=a.seed, snr=a.snr, host=os.uname()[1], qbits=QBITS, key_tag=KEY_TAG)
        tmp = os.path.join(d, '.tmp_b%05d.npz' % bi)
        np.savez_compressed(tmp, biterr=bev.numpy().astype(np.uint8), err_idx=err.numpy().astype(np.int32),
                            xhat=lh[err].numpy().astype(np.int8), anneals=ann.astype(np.float32), info=np.array(json.dumps(info)))
        os.rename(tmp, fn)
        print(time.strftime('%m-%d %H:%M:%S'), a.tag, method, 'batch', bi, 'err uses', int(err.numel()), 'bit err', int(bev.sum()),
              '%.1f s' % info['wall'], 'over13', cs['over13'], flush=True)
    print('DONE', a.tag, method, a.b0, a.b1, flush=True)


if __name__ == '__main__':
    main()
