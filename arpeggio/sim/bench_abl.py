#!/usr/bin/env python3
"""PROTOCOL.md 4.5 timing pass (B200 GPU7 ONLY, in a window with no other process of ours on GPU7; label
"non-exclusive host"). NVML idle of the GPU (30 s, before any CUDA context), then per item: one untimed call and
REPS segments, each ending with the first call past MIN_S seconds; the solver wrapped in mdi_solvers.Timed
(synchronised before/after every call) gives the in-chain solver time; the chain time is the wall time of the
segment. Items: every ablation variant (PyTorch) at P1-P3; the int16 kernel for (i), (ii), (iii), (vii) at P1 and P3;
MMSE and MMSE-SIC chains at 31.02 dB (16x16 16-QAM, regime map). Draws: apx.draw seed 106, two batches cycled.
Usage: bench_abl.py --tuned results/tuned.json --out results/timing/bench [--only ID,ID]"""
import argparse
import ctypes
import json
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument('--tuned', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--min-s', type=float, default=6.0)
ap.add_argument('--reps', type=int, default=3)
ap.add_argument('--idle-s', type=float, default=30.0)
ap.add_argument('--only', default='')
ap.add_argument('--dry', action='store_true', help='code smoke test on any GPU (numbers discarded, never reported)')
a = ap.parse_args()
assert a.dry or os.environ.get('MIMO_GPU_UUID') == '<GPU_UUID>', 'timing runs on hostA GPU7 only'
if a.dry:
    a.min_s, a.reps, a.idle_s = 0.0, 1, 1.0
nv = ctypes.CDLL('libnvidia-ml.so.1')
assert nv.nvmlInit_v2() == 0
hdl = ctypes.c_void_p()
assert nv.nvmlDeviceGetHandleByUUID(os.environ['MIMO_GPU_UUID'].encode(), ctypes.byref(hdl)) == 0


def joules():
    e = ctypes.c_ulonglong()
    assert nv.nvmlDeviceGetTotalEnergyConsumption(hdl, ctypes.byref(e)) == 0
    return e.value * 1e-3


os.makedirs(os.path.dirname(a.out), exist_ok=True)
fo = open(a.out + '.jsonl', 'a')


def emit(r):
    fo.write(json.dumps(r) + '\n'); fo.flush(); print(json.dumps(r), flush=True)


e0, t0 = joules(), time.time()
time.sleep(a.idle_s)
idle = dict(seg='idle_noproc', seconds=time.time() - t0, energy_J=joules() - e0)
idle['avg_W'] = idle['energy_J'] / idle['seconds']
emit(idle)
P_IDLE = idle['avg_W']

import torch  # noqa: E402

import anefx  # noqa: E402
import apx  # noqa: E402
import mdi_solvers as ms  # noqa: E402
import mimo  # noqa: E402

ka = anefx.Kernel(os.environ['ANE_CUBIN'])
ctx = apx.Ctx(json.load(open(a.tuned)))
PTS = {'P1': ('x16', 20.0, 32, 500), 'P2': ('x32', 22.0, 8, 250), 'P3': ('q32', 14.0, 8, 2000)}
VAR = ['mdiane', 'abl_noalt', 'abl_noaltq0', 'abl_q0', 'abl_qdim', 'abl_dil', 'abl_final', 'abl_ons', 'abl_pimi', 'abl_sa',
       'abl_sym', 'abl_symw']
KER = {'mdiane': (True, 0.4, 0.0), 'abl_noalt': (False, 0.4, 0.0), 'abl_q0': (True, 0.0, 0.0), 'abl_ons': (True, 0.4, apx.KAPPA_ONS)}
items = []
for pt, (sh, snr, Ns, B) in PTS.items():
    for v in VAR:
        m = ('mdiane%d' % Ns) if v == 'mdiane' else '%s_%d' % (v, Ns)
        items.append(dict(id='%s_%s_torch' % (pt, v), point=pt, shape=sh, snr=snr, Ns=Ns, batch=B, method=m, impl='torch'))
    if pt in ('P1', 'P3'):
        for v in KER:
            items.append(dict(id='%s_%s_kernel' % (pt, v), point=pt, shape=sh, snr=snr, Ns=Ns, batch=B, method=v, impl='kernel'))
for m in ('mmse', 'sic'):
    items.append(dict(id='P4_%s_torch' % m, point='P4', shape='x16', snr=31.02, Ns=None, batch=500, method=m, impl='torch'))
only = set(x for x in a.only.split(',') if x)


def cpu_s():
    t = os.times()
    return t.user + t.system


for it in items:
    if only and it['id'] not in only:
        continue
    s = apx.SHAPES[it['shape']]
    bs = [apx.draw(106, it['snr'], k, it['batch'], s['nt'], s['M']) for k in range(2)]
    gs = torch.Generator(device='cuda'); gs.manual_seed(106_000_003)
    calls = [0]
    if it['impl'] == 'kernel':
        alt, q, kap = KER[it['method']]

        def raw(I, na, K):
            calls[0] += 1
            F = anefx.to_fixed(I, apx.MA['Sk'] * 2 * K, apx.MA['t0'], apx.MA['t1'], q, kap)
            return ka.anechoic(F, na, 106_000 + 1000 * calls[0], P=2 * K if alt else 1, mode='chains')[0].float()
        solver, tl, Ns = ms.Timed(raw), None, it['Ns']
    elif it['method'] in ('mmse', 'sic'):
        solver = None
    else:
        raw, tl, Ns = apx.mdi_solver_for(it['method'], it['shape'], gs, ctx)
        solver = ms.Timed(raw)
    c = s['mdi']

    def call(i):
        b = bs[i % 2]
        if solver is None:
            lh, _, _ = apx.detect(it['method'], b, it['shape'], gs, ctx)
        else:
            lh, _ = apx.mdi_diag(b, solver, it['Ns'], c['Rmax'], c['S'], guesses=c['guesses'], to_levels=tl)
        return mimo.bit_errors(b, lh)
    call(0); torch.cuda.synchronize()
    i = 1
    for rep in range(a.reps):
        err = bits = nd = 0
        if solver is not None:
            solver.t = 0.0
        torch.cuda.synchronize()
        c1, e1, t1 = cpu_s(), joules(), time.time()
        while True:
            e_, n_ = call(i); i += 1
            err += e_; bits += n_; nd += it['batch']
            torch.cuda.synchronize()
            if time.time() - t1 >= a.min_s:
                break
        t2, e2, c2 = time.time(), joules(), cpu_s()
        sec, ej = t2 - t1, e2 - e1
        st = solver.t if solver is not None else 0.0
        emit(dict(seg='chain', label='non-exclusive host', rep=rep, detections=nd, seconds=sec, ms_per_det=1e3 * sec / nd,
                  solver_ms_per_det=1e3 * st / nd, rest_ms_per_det=1e3 * (sec - st) / nd, energy_J=ej, avg_W=ej / sec,
                  mJ_per_det=1e3 * ej / nd, mJ_per_det_above_idle=1e3 * (ej - P_IDLE * sec) / nd, cpu_s=c2 - c1,
                  ber_timed=err / bits, gpu=torch.cuda.get_device_name(0), **it))
    del bs
    torch.cuda.empty_cache()
