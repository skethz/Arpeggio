#!/usr/bin/env python3
"""Milestone-C timed cohort (PROTOCOL_C.md): NVML idle of the GPU before any CUDA context; then per PLAN item
- mode 'chain': the whole MDI-MIMO chain (MMSE, MMSE-SIC, radius, dDI mapping, solver calls, selection, orchestration)
  on batches of fresh draws (up to NB distinct batches cycled), the solver wrapped in a synchronised timer;
- mode 'solver': the solver calls captured from one untimed chain run per batch (inputs I, na, K), replayed back to
  back, i.e. solver-only work;
each as one untimed run, then REPS segments, a segment being back-to-back calls until at least MIN_S seconds have
elapsed (time-based: the segment ends with the first call that crosses MIN_S); NVML's total-energy counter at the
segment bounds; detections/s, J per detection (total, above the no-process idle), solver seconds inside the chain,
process CPU seconds, BER of the timed detections (chain). JSON lines to OUT.jsonl.
Usage: bench_c.py --plan PLAN_C.json --ane-cubin C1 --ahc-cubin C2 --out PREFIX"""
import argparse
import ctypes
import json
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument('--plan', required=True)
ap.add_argument('--ane-cubin', required=True)
ap.add_argument('--ahc-cubin', required=True)
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

import ahcfx  # noqa: E402
import anefx  # noqa: E402
import mdi_solvers as ms  # noqa: E402
import mimo  # noqa: E402

torch.backends.cuda.matmul.allow_tf32 = False
ka = anefx.Kernel(a.ane_cubin)
kh = ahcfx.AhcKernel(a.ahc_cubin)
only = set(x for x in a.only.split(',') if x)


def cpu_s():
    t = os.times()
    return t.user + t.system


for it in plan['items']:
    if only and it['id'] not in only:
        continue
    impl = it['method'] + '_' + it['impl']                                # ahc_torch, ane_kernel, ...
    cfg = ms.MDI[(it['shape'], it['M'])]
    B, NB = it['batch'], it.get('nb', 4)
    g = torch.Generator(device='cuda'); g.manual_seed(it.get('seed', 31_000_003))
    bs = [mimo.make_batch(B, it['nt'], it['nt'], it['M'], it['snr'], g) for _ in range(NB)]
    gs = torch.Generator(device='cuda'); gs.manual_seed(it.get('seed', 31_000_003) + 7919)
    solver = ms.Timed(ms.make_solver(impl, gs, ka, kh, seed0=31_000_000), capture=(it['mode'] == 'solver'))
    if it['mode'] == 'solver':                                            # capture the calls of one chain per batch
        caps = []
        for b in bs:
            solver.kept = []
            ms.detect(b, impl, it['Ns'], cfg, solver)
            caps.append(solver.kept)
        solver.capture = False
        torch.cuda.synchronize()

        def call(i):
            for I, na, K in caps[i % len(caps)]:
                solver.solver(I, na, K)
            return 0, 0
    else:
        def call(i):
            lh, st = ms.detect(bs[i % NB], impl, it['Ns'], cfg, solver)
            return mimo.bit_errors(bs[i % NB], lh)
    call(0); torch.cuda.synchronize()                                     # untimed
    i = 1
    for rep in range(a.reps):
        err = bits = nd = 0
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
        r = dict(seg=it['mode'], id=it['id'], point=it.get('point'), t_start=t1, t_end=t2, shape=it['shape'], M=it['M'], snr=it['snr'],
                 Ns=it['Ns'], method=it['method'], impl=it['impl'], rep=rep, batch=B, detections=nd, seconds=sec,
                 det_per_s=nd / sec, ms_per_det=1e3 * sec / nd, energy_J=ej, avg_W=ej / sec, mJ_per_det=1e3 * ej / nd,
                 mJ_per_det_above_idle=1e3 * (ej - P_IDLE * sec) / nd, cpu_s=c2 - c1, cpu_ms_per_det=1e3 * (c2 - c1) / nd)
        if it['mode'] == 'chain':
            r.update(ber=err / bits, solver_s=solver.t, solver_ms_per_det=1e3 * solver.t / nd,
                     rest_ms_per_det=1e3 * (sec - solver.t) / nd)
        emit(r)
    del bs, solver
    torch.cuda.empty_cache()
