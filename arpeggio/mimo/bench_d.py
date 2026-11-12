#!/usr/bin/env python3
"""Milestone-D timed cohort (PROTOCOL_D.md), structured as bench_c.py: NVML idle of the GPU before any CUDA context;
then per PLAN item one untimed call and REPS segments, each a run of back-to-back calls ending with the first call that
brings the elapsed time to at least MIN_S seconds; NVML's total-energy counter at the segment bounds; detections/s,
ms and mJ per detection (total and above the no-process idle), solver seconds inside the chain, process CPU seconds,
BER of the timed detections (chain modes). Methods and implementations:
  pimi    PIMI chain (their MMSE, DI mapping, fixed point, solver, selection, reconstruction): torch | kernel;
          mode 'solver' = the solver alone on prepared fixed-point problems (kernel: the platform row)
  ane_mdi Antiphase in the MDI wrapper (formerly MDI-Anechoic; mdi_solvers 'ane_torch' / 'ane_kernel')
  ane_ss  Antiphase, one delta stage (dDI K = 1 around MMSE, S 256, T 0.3, q 0.4, 2 phases), R anneals
  abl     ablation of Antiphase in MDI: variant i / ii / iii / iv (alternating copies on/off, kappa 0 / 0.3)
Usage: bench_d.py --plan PLAN_D.json --ane-cubin C1 --pimi-cubin C2 --out PREFIX"""
import argparse
import ctypes
import json
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument('--plan', required=True)
ap.add_argument('--ane-cubin', required=True)
ap.add_argument('--pimi-cubin', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--min-s', type=float, default=6.0)
ap.add_argument('--reps', type=int, default=3)
ap.add_argument('--idle-s', type=float, default=30.0)
ap.add_argument('--only', default='', help='comma list of item ids (development)')
a = ap.parse_args()
plan = json.load(open(a.plan))

nv = ctypes.CDLL('libnvidia-ml.so.1')
assert nv.nvmlInit_v2() == 0
hdl = ctypes.c_void_p()
assert nv.nvmlDeviceGetHandleByUUID(os.environ['MIMO_GPU_UUID'].encode(), ctypes.byref(hdl)) == 0


def joules():
    e = ctypes.c_ulonglong()
    assert nv.nvmlDeviceGetTotalEnergyConsumption(hdl, ctypes.byref(e)) == 0
    return e.value * 1e-3


fo = open(a.out + '.jsonl', 'a')


def emit(r):
    fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)


e0, t0 = joules(), time.time()
time.sleep(a.idle_s)
idle = dict(seg='idle_noproc', t_start=t0, t_end=time.time(), seconds=time.time() - t0, energy_J=joules() - e0)
idle['avg_W'] = idle['energy_J'] / idle['seconds']
emit(idle)
P_IDLE = idle['avg_W']

import torch  # noqa: E402

import anefx  # noqa: E402
import mdi_solvers as ms  # noqa: E402
import mimo  # noqa: E402
import pimi  # noqa: E402

torch.backends.cuda.matmul.allow_tf32 = False
ka = anefx.Kernel(a.ane_cubin)
kp = pimi.PimiKernel(a.pimi_cubin)
only = set(x for x in a.only.split(',') if x)
MA = ms.MDIANE
KAPPA_A = 0.3
ABL = {'i': (True, 0.0), 'ii': (False, 0.0), 'iii': (True, KAPPA_A), 'iv': (False, KAPPA_A)}


def cpu_s():
    t = os.times()
    return t.user + t.system


def abl_solver(impl, alt, kappa, gs, seed0):
    calls = [0]
    if impl == 'torch':
        return lambda I, na, K: mimo.anechoic(I, na, MA['Sk'] * 2 * K, MA['t0'], MA['t1'], MA['q'], kappa=kappa, gen=gs,
                                              phases=2 * K if alt else 1)

    def f(I, na, K):
        calls[0] += 1
        F = anefx.to_fixed(I, MA['Sk'] * 2 * K, MA['t0'], MA['t1'], MA['q'], kappa)
        return ka.anechoic(F, na, seed0 + 1000 * calls[0], P=2 * K if alt else 1, mode='chains')[0].float()
    return f


for it in plan['items']:
    if only and it['id'] not in only:
        continue
    B, NB, M = it['batch'], it.get('nb', 2), it['M']
    seed = it.get('seed', 41_000_003)
    g = torch.Generator(device='cuda'); g.manual_seed(seed)
    bs = [mimo.make_batch(B, it['nt'], it['nt'], M, it['snr'], g) for _ in range(NB)]
    gs = torch.Generator(device='cuda'); gs.manual_seed(seed + 7919)
    ctr = [0]
    timer = dict(t=0.0)
    meth, impl, mode = it['method'], it['impl'], it['mode']

    def tsync(fn, *x):
        torch.cuda.synchronize(); t_ = time.time()
        out = fn(*x)
        torch.cuda.synchronize(); timer['t'] += time.time() - t_
        return out

    if meth == 'pimi':
        steps = it['steps']
        beta, gamma = pimi.SCHED[it.get('sched') or pimi.sched_name(it['nt'], M)]
        if impl == 'torch':
            solve = lambda P: pimi.select(P, *pimi.pimi_torch(P, steps, pimi.TRIALS, gs, beta=beta, gamma=gamma))
        else:
            def solve(P):
                ctr[0] += 1
                return kp.pimi(P, steps, pimi.TRIALS, seed + 1000 * ctr[0], mode='best', warps=it.get('warps', 8),
                               beta=beta, gamma=gamma)[0].to(torch.int64)
        if mode == 'solver':
            Ps = [pimi.problem(b, pimi.slice_levels(pimi.mmse_z(b), M)) for b in bs]
            torch.cuda.synchronize()

            def call(i):
                solve(Ps[i % NB])
                return 0, 0
        else:
            def call(i):
                b = bs[i % NB]
                P = pimi.problem(b, pimi.slice_levels(pimi.mmse_z(b), M))
                sb = tsync(solve, P)
                return mimo.bit_errors(b, pimi.decide(P, sb, M))
    elif meth in ('ane_mdi', 'abl'):
        cfg = ms.MDI[(it['shape'], M)]
        if meth == 'ane_mdi':
            raw = ms.make_solver('ane_' + impl, gs, ka, None, seed0=seed - 3)
        else:
            alt, kap = ABL[it['variant']]
            raw = abl_solver(impl, alt, kap, gs, seed - 3)
        solver = ms.Timed(raw)

        def call(i):
            b = bs[i % NB]
            lh, st = ms.detect(b, 'ane_' + impl, it['Ns'], cfg, solver)
            return mimo.bit_errors(b, lh)
    elif meth == 'ane_ss':
        R = it['R']

        def solve_ss(Id):
            if impl == 'torch':
                return mimo.anechoic(Id, R, 2 * MA['Sk'], MA['t0'], MA['t1'], MA['q'], kappa=0.0, gen=gs, phases=2)
            ctr[0] += 1
            F = anefx.to_fixed(Id, 2 * MA['Sk'], MA['t0'], MA['t1'], MA['q'], 0.0)
            return ka.anechoic(F, R, seed + 1000 * ctr[0], P=2, mode='chains')[0].float()

        def call(i):
            b = bs[i % NB]
            z, Ai, _ = mimo.mmse(b)
            lm = mimo.mmse_hard(b, z, Ai)
            Id = mimo.ising_delta(b, z, K=1)
            S_ = tsync(solve_ss, Id)
            lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, M), lm)
            return mimo.bit_errors(b, lh)
    else:
        raise SystemExit('unknown method ' + meth)
    call(0); torch.cuda.synchronize()                                     # untimed
    i = 1
    for rep in range(a.reps):
        err = bits = nd = 0
        timer['t'] = 0.0
        if meth in ('ane_mdi', 'abl'):
            solver.t = 0.0
        torch.cuda.synchronize()
        c1, e1, t1 = cpu_s(), joules(), time.time()
        while True:
            e_, n_ = call(i); i += 1
            err += e_; bits += n_; nd += B
            torch.cuda.synchronize()
            if time.time() - t1 >= a.min_s:
                break
        t2, e2, c2 = time.time(), joules(), cpu_s()
        sec, ej = t2 - t1, e2 - e1
        st_ = solver.t if meth in ('ane_mdi', 'abl') else timer['t']
        r = dict(seg=mode, id=it['id'], point=it.get('point'), t_start=t1, t_end=t2, shape=it['shape'], M=M,
                 snr=it['snr'], method=meth, impl=impl, steps=it.get('steps'), Ns=it.get('Ns'), R=it.get('R'),
                 variant=it.get('variant'), rep=rep, batch=B, detections=nd, seconds=sec, det_per_s=nd / sec,
                 ms_per_det=1e3 * sec / nd, energy_J=ej, avg_W=ej / sec, mJ_per_det=1e3 * ej / nd,
                 mJ_per_det_above_idle=1e3 * (ej - P_IDLE * sec) / nd, cpu_s=c2 - c1, cpu_ms_per_det=1e3 * (c2 - c1) / nd)
        if mode == 'chain':
            r.update(ber=err / bits, solver_s=st_, solver_ms_per_det=1e3 * st_ / nd, rest_ms_per_det=1e3 * (sec - st_) / nd)
        emit(r)
    del bs
    torch.cuda.empty_cache()
