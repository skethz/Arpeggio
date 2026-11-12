#!/usr/bin/env python3
"""Throughput and energy of the GPU detectors on GPU6 (PROTOCOL.md). First 30 s of idle from NVML before any CUDA
context exists; then, per configuration and method, one untimed batch, then REPS timed segments, each a run of
batches of the same size (fresh channel draws, up to 8 distinct batches cycled) lasting at least MIN_S seconds;
NVML total-energy counter at the segment bounds; detections/s, J per detection (total and above the no-process idle)
and the BER of the timed detections; then the mean number of spin flips per (half-)step and chain of the tuned
Anechoic schedule (a separate instrumented batch). JSON lines to OUT.jsonl. Usage: bench.py --out PREFIX"""
import argparse
import ctypes
import json
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--min-s', type=float, default=6.0)
ap.add_argument('--reps', type=int, default=3)
ap.add_argument('--idle-s', type=float, default=30.0)
a = ap.parse_args()

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

import torch  # noqa: E402  (after the idle segment: no CUDA context before)

import mimo  # noqa: E402

torch.backends.cuda.matmul.allow_tf32 = False
CFG = [  # (name, Nt, M, SNR, batch, Anechoic schedule, CIM A_s, methods): operating points from the BER sweeps
    ('q16', 16, 4, 12.0, 20000, dict(S=128, t0=0.7, t1=0.5, q=0.6, kappa=0, phases=1), 1.0,
     ['mmse', 'ane16', 'ane64', 'cim64', 'ahc64']),
    ('x16', 16, 16, 22.0, 20000, dict(S=256, t0=0.3, t1=0.3, q=0.4, kappa=0, phases=2), 1.5,
     ['mmse', 'aned16', 'aned64', 'ahcd64']),
]


def run(method, b, an, cas, gs):
    z, Ai, el2 = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    if method == 'mmse':
        return lm
    if method[3:4] == 'd':                                                 # delta formulation (dDI, K = 1)
        Id = mimo.ising_delta(b, z, K=1)
        na = int(method[4:])
        if method.startswith('aned'):
            S_ = mimo.anechoic(Id, na, an['S'], an['t0'], an['t1'], an['q'], kappa=an['kappa'], gen=gs, phases=an['phases'])
        else:
            S_ = mimo.ahc(Id, na, gen=gs)
        lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, b['M']), lm)
        return lh
    I = mimo.ising(b, z)
    na = int(method[3:])
    if method.startswith('ane'):
        S_ = mimo.anechoic(I, na, an['S'], an['t0'], an['t1'], an['q'], kappa=an['kappa'], gen=gs)
    elif method.startswith('cim'):
        S_ = mimo.cim(I, na, As=cas, pump='time', gen=gs)
    else:
        S_ = mimo.ahc(I, na, gen=gs)
    lh, _, _ = mimo.select(b, mimo.spins_to_levels(S_, b['M'], b['H'].shape[-1]), lm)
    return lh


for name, Nt, M, snr, B, an, cas, methods in CFG:
    for method in methods:
        g = torch.Generator(device='cuda'); g.manual_seed(77)
        gs = torch.Generator(device='cuda'); gs.manual_seed(78)
        b = mimo.make_batch(B, Nt, Nt, M, snr, g)
        run(method, b, an, cas, gs); torch.cuda.synchronize()            # untimed
        t = time.time(); run(method, b, an, cas, gs); torch.cuda.synchronize(); per = time.time() - t
        nrep = max(1, int(a.min_s / max(per, 1e-6)) + 1)
        for rep in range(a.reps):
            err = bits = 0
            batches = [mimo.make_batch(B, Nt, Nt, M, snr, g) for _ in range(min(nrep, 8))]
            torch.cuda.synchronize()
            e1, t1 = joules(), time.time()
            for i in range(nrep):
                bb = batches[i % len(batches)]
                lh = run(method, bb, an, cas, gs)
                e_, n_ = mimo.bit_errors(bb, lh); err += e_; bits += n_
            torch.cuda.synchronize()
            t2, e2 = time.time(), joules()
            sec, ej, ndet = t2 - t1, e2 - e1, nrep * B
            emit(dict(seg='detect', cfg=name, nt=Nt, M=M, snr=snr, method=method, rep=rep, detections=ndet, seconds=sec,
                      energy_J=ej, avg_W=ej / sec, det_per_s=ndet / sec, J_per_det=ej / ndet,
                      J_per_det_above_idle=(ej - P_IDLE * sec) / ndet, ber=err / bits, batch=B,
                      ane=an if method.startswith('ane') else None, cim_as=cas if method.startswith('cim') else None))
    # flips per (half-)step and chain of the tuned Anechoic schedule (instrumented, not timed)
    g = torch.Generator(device='cuda'); g.manual_seed(79)
    b = mimo.make_batch(2000, Nt, Nt, M, snr, g)
    z, Ai, el2 = mimo.mmse(b)
    I = mimo.ising_delta(b, z, K=1) if an['phases'] > 1 else mimo.ising(b, z)
    gs = torch.Generator(device='cuda'); gs.manual_seed(80)
    h, J = I['h'], I['J']
    N = h.shape[1]
    T = mimo.geom(an['t0'], an['t1'], an['S'], 'cuda')
    s = torch.where(torch.rand(2000, 16, N, generator=gs, device='cuda') < 0.5, -1.0, 1.0)
    flips = []
    for k in range(an['S']):
        u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
        z_ = s * u + an['q']
        rr = (torch.rand(s.shape, generator=gs, device='cuda') - 0.5) * 4 * T[k]
        f = z_ < rr
        if an['phases'] > 1:
            idx = torch.arange(N, device='cuda') // (N // an['phases'])
            f = f & (idx == (k % an['phases']))
        flips.append(float(f.float().sum(-1).mean()))
        s = torch.where(f, -s, s)
    emit(dict(seg='flips', cfg=name, spins=int(N), steps=an['S'], mean_flips_per_step=sum(flips) / len(flips),
              flips_first10=sum(flips[:10]) / 10, flips_last64=sum(flips[-64:]) / 64))
