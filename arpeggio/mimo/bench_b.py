#!/usr/bin/env python3
"""Milestone-B timed cohort (PROTOCOL_B.md): NVML idle of GPU6 before any CUDA context, then the GPU items of PLAN
(the custom kernel: 'e2e' = MMSE + Ising mapping + fixed point + kernel + selection, 'kernel' = the kernel call alone
on precomputed fixed-point problems, 'mmse' = MMSE alone), each as REPS segments of back-to-back batches lasting at
least MIN_S seconds (up to 8 distinct batches of fresh draws cycled), NVML energy at the segment bounds; then the
CPU items (K-best K* with numba on all CPU threads; wall time only: RAPL is root-only), same segment rule, with the
load average; then instrumented (untimed) kernel runs for flips per step. JSON lines to OUT.jsonl.
Usage: bench_b.py --plan PLAN.json --cubin CUBIN --out PREFIX"""
import argparse
import ctypes
import json
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument('--plan', required=True)
ap.add_argument('--cubin', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--min-s', type=float, default=6.0)
ap.add_argument('--reps', type=int, default=3)
ap.add_argument('--idle-s', type=float, default=30.0)
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
idle = dict(seg='idle_noproc', seconds=time.time() - t0, energy_J=joules() - e0)
idle['avg_W'] = idle['energy_J'] / idle['seconds']
emit(idle)
P_IDLE = idle['avg_W']

import numpy as np  # noqa: E402
import torch  # noqa: E402

import anefx  # noqa: E402
import fxdetect  # noqa: E402
import mimo  # noqa: E402
import tree  # noqa: E402

torch.backends.cuda.matmul.allow_tf32 = False
kern = anefx.Kernel(a.cubin)


def segments(name, fn, nb, B, extra, gpu=True):
    """fn(i) runs batch i (cycled over nb prepared batches) and returns (bit errors, bits)."""
    fn(0)
    if gpu:
        torch.cuda.synchronize()
    t = time.time(); fn(1 % nb)
    if gpu:
        torch.cuda.synchronize()
    per = time.time() - t
    nrep = max(1, int(a.min_s / max(per, 1e-6)) + 1)
    for rep in range(a.reps):
        err = bits = 0
        la0 = os.getloadavg()
        if gpu:
            torch.cuda.synchronize()
        e1, t1 = joules(), time.time()
        for i in range(nrep):
            e_, n_ = fn(i % nb); err += e_; bits += n_
        if gpu:
            torch.cuda.synchronize()
        t2, e2 = time.time(), joules()
        sec, ej, nd = t2 - t1, e2 - e1, nrep * B
        r = dict(seg=name, rep=rep, detections=nd, seconds=sec, det_per_s=nd / sec, us_per_det=1e6 * sec / nd,
                 ber=err / bits if bits else None, batch=B, loadavg_start=la0[0], loadavg_end=os.getloadavg()[0])
        if gpu:
            r.update(energy_J=ej, avg_W=ej / sec, J_per_det=ej / nd, J_per_det_above_idle=(ej - P_IDLE * sec) / nd)
        r.update(extra)
        emit(r)


for it in plan['gpu']:
    sc = dict(it['sched'], kind=it.get('kind', 'ri' if it['M'] == 4 else 'ddi'), Nt=it['nt'], Nr=it['nr'], M=it['M'])
    B = it['batch']
    g = torch.Generator(device='cuda'); g.manual_seed(it.get('seed', 4242))
    bs = [mimo.make_batch(B, it['nt'], it['nr'], it['M'], it['snr'], g, rho=it.get('rho', 0.0)) for _ in range(8)]
    zs = [mimo.mmse(b)[:2] for b in bs]
    extra = {k: it[k] for k in ('name', 'nt', 'nr', 'M', 'snr', 'mode') if k in it}
    extra.update(rho=it.get('rho', 0.0), anneals=it.get('R'), sched=it['sched'], kind=sc['kind'])
    if it['mode'] == 'mmse':
        def fn(i):
            z, Ai, _ = mimo.mmse(bs[i])
            return mimo.bit_errors(bs[i], mimo.mmse_hard(bs[i], z, Ai))
    elif it['mode'] == 'e2e':
        def fn(i):
            lh = fxdetect.detect(bs[i], sc, it['R'], kern, seed=777 + i)
            return mimo.bit_errors(bs[i], lh)
    else:                                                                  # kernel only
        Fs, Ps = [], []
        for b, (z, Ai) in zip(bs, zs):
            if sc['kind'] == 'ri':
                I = mimo.ising(b, z); Ps.append(1)
            else:
                I = mimo.ising_delta_at(b, mimo.mmse_hard(b, z, Ai), 1); Ps.append(2)
            Fs.append(anefx.to_fixed(I, sc['S'], sc['t0'], sc['t1'], sc['q'], sc.get('kappa', 0.0)))
        mode = 'best' if sc['kind'] == 'ri' else 'chains'

        def fn(i):
            kern.anechoic(Fs[i], it['R'], 777 + i, P=Ps[i], mode=mode)
            return 0, 0
    segments('gpu_' + it['mode'], fn, 8, B, extra)
    del bs, zs
    torch.cuda.empty_cache()

for it in plan['cpu']:
    B = it['batch']
    g = torch.Generator(device='cuda'); g.manual_seed(it.get('seed', 4343))
    bs = [mimo.make_batch(B, it['nt'], it['nr'], it['M'], it['snr'], g, rho=it.get('rho', 0.0)) for _ in range(8)]
    Hs = [(b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy(), b['l'].cpu().numpy()) for b in bs]
    lv = np.array(mimo.PAM[it['M']]['levels'], np.float64)
    bt = [mimo.levels_to_bits(torch.tensor(l), it['M']).numpy() for _, _, l in Hs]

    def fn(i, K=it['K']):
        xh, _ = tree.kbest2(Hs[i][0], Hs[i][1], lv, K)
        bh = mimo.levels_to_bits(torch.tensor(xh, dtype=torch.float32), it['M']).numpy()
        return int((bh != bt[i]).sum()), bt[i].size
    extra = {k: it[k] for k in ('name', 'nt', 'nr', 'M', 'snr', 'K') if k in it}
    extra.update(rho=it.get('rho', 0.0), threads=int(os.environ.get('NUMBA_NUM_THREADS', os.cpu_count())))
    segments('cpu_kbest', fn, 8, B, extra, gpu=False)

for it in plan.get('flips', []):
    sc = dict(it['sched'], kind=it.get('kind', 'ri' if it['M'] == 4 else 'ddi'), Nt=it['nt'], Nr=it['nr'], M=it['M'])
    g = torch.Generator(device='cuda'); g.manual_seed(4444)
    b = mimo.make_batch(it['batch'], it['nt'], it['nr'], it['M'], it['snr'], g, rho=it.get('rho', 0.0))
    st = torch.zeros(4, dtype=torch.int64, device='cuda')
    fxdetect.detect(b, sc, it['R'], kern, seed=999, stats=st)
    torch.cuda.synchronize()
    fl, ev, rng, steps = [int(x) for x in st.tolist()]
    P = 1 if sc['kind'] == 'ri' else 2
    N = 2 * it['nt'] * (1 if it['M'] == 4 else 2) if sc['kind'] == 'ri' else 4 * it['nt']
    emit(dict(seg='flips', name=it['name'], kind=sc['kind'], nt=it['nt'], nr=it['nr'], M=it['M'], snr=it['snr'],
              anneals=it['R'], spins=N, phases=P, steps=sc['S'], flips_per_step_anneal=fl / steps,
              energy_updates_per_step=ev / steps, philox_blocks_per_step_anneal=rng / steps,
              flips_per_detection=fl / it['batch'], decisions_per_detection=steps / it['batch'] * N / P,
              field_macs_per_detection=fl / it['batch'] * N))
