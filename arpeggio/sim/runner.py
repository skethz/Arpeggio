#!/usr/bin/env python3
"""Checkpointed error-counting worker (PROTOCOL.md sections 3-4). Pulls point jobs (shape, method, SNR) from a plan in
priority order, claims each with an exclusive claim file, and runs it batch by batch until the stopping rule holds:
>= min_vec erroneous channel uses AND >= min_bit bit errors AND >= min_uses uses, or the bit cap (1e7 bits).
Every batch is saved as its own .npz (atomic rename) with the per-use bit-error vector, and for each erroneous use:
its index, ||y - H x_hat||^2, ||y - H x_true||^2 (float64), x_hat, and the wrapper's search-region diagnostics.
A restarted worker resumes from the saved batches; nothing is ever overwritten.
Usage: runner.py --plan PLAN.json --root RESULTS_DIR --worker NAME [--only-cpu | --no-cpu] [--max-jobs N]"""
import argparse
import hashlib
import json
import os
import socket
import sys
import time

import numpy as np
import torch

ap = argparse.ArgumentParser()
ap.add_argument('--plan', required=True)
ap.add_argument('--root', required=True)
ap.add_argument('--worker', required=True)
ap.add_argument('--cpu-jobs', choices=('only', 'no', 'any'), default='any', help='K-best / SD jobs (numba CPU)')
ap.add_argument('--threads', type=int, default=2)
ap.add_argument('--max-jobs', type=int, default=10 ** 9)
ap.add_argument('--filter', default='', help='comma list of substrings; job id must contain one')
a = ap.parse_args()
torch.set_num_threads(a.threads)

import apx  # noqa: E402

plan = json.load(open(a.plan))
HOST = socket.gethostname().split('.')[0]
CPU_METHODS = ('kbest', 'sd')
log = lambda *x: print(time.strftime('%m-%d %H:%M:%S'), a.worker, *x, flush=True)


def job_dir(j):
    return os.path.join(a.root, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def claim(j):
    d = job_dir(j)
    os.makedirs(d, exist_ok=True)
    if os.path.exists(os.path.join(d, 'done.json')):
        return False
    cf = os.path.join(d, 'claim.json')
    for _ in range(2):
        try:
            fd = os.open(cf, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps(dict(worker=a.worker, host=HOST, pid=os.getpid(), t=time.time())).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                c = json.load(open(cf))
            except Exception:
                return False
            if c.get('host') == HOST and not pid_alive(int(c.get('pid', -1))):   # stale claim of a dead worker
                os.rename(cf, cf + '.stale.%d' % int(time.time()))
                continue
            return False
    return False


def mhash(m):
    return int(hashlib.sha256(m.encode()).hexdigest()[:8], 16) % 1_000_000


def bits_per_use(shape):
    s = apx.SHAPES[shape]
    return 2 * s['nt'] * (1 if s['M'] == 4 else 2)


def tally(d):
    files = sorted(f for f in os.listdir(d) if f.startswith('b') and f.endswith('.npz'))
    n = ve = be = 0
    sec = 0.0
    for f in files:
        z = np.load(os.path.join(d, f), allow_pickle=False)
        x = z['biterr']
        n += len(x); ve += int((x > 0).sum()); be += int(x.sum())
        sec += float(json.loads(str(z['info']))['seconds'])
    return len(files), n, ve, be, sec


def run_job(j, ctx):
    d = job_dir(j)
    shape, method, snr, seed = j['shape'], j['method'], float(j['snr']), int(j['seed'])
    s = apx.SHAPES[shape]
    nt, M = s['nt'], s['M']
    bpu = bits_per_use(shape)
    B = int(j['batch'])
    max_uses = int(j.get('max_bits', 1e7)) // bpu
    min_vec, min_bit, min_uses = int(j.get('min_vec', 100)), int(j.get('min_bit', 100)), int(j.get('min_uses', 0))
    nb, n, ve, be, sec = tally(d)
    while True:
        if (ve >= min_vec and be >= min_bit and n >= min_uses) or n >= max_uses:
            break
        bi = nb
        m = min(B, max_uses - n)
        b = apx.draw(seed, snr, bi, B, nt, M)
        if m < B:
            for k in ('H', 'y', 'l'):
                b[k] = b[k][:m].contiguous()
        gs = torch.Generator(device='cuda'); gs.manual_seed(apx.draw_seed(seed, snr, bi) + 7919 + mhash(method))
        torch.cuda.synchronize(); t0 = time.time()
        z, Ai, _ = apx.mimo.mmse(b)
        lh, dg, info = apx.detect(method, b, shape, gs, ctx, z=z)
        torch.cuda.synchronize(); dt = time.time() - t0
        bev = apx.biterr_per_use(b, lh)
        err = torch.nonzero(bev > 0).flatten()
        bd = dict(H=b['H'].double(), y=b['y'].double(), l=b['l'].double())
        out = dict(biterr=bev.cpu().numpy().astype(np.uint8), err_idx=err.cpu().numpy().astype(np.int32),
                   d_hat=apx.dist_of(bd, lh.double())[err].cpu().numpy(), d_true=apx.dist_true(bd)[err].cpu().numpy(),
                   xhat=lh[err].cpu().numpy().astype(np.int8))
        if dg is not None:
            for k, v in dg.items():
                if k == 'uncert':
                    out['uncert_idx'] = torch.nonzero(v).flatten().cpu().numpy().astype(np.int32)
                elif k == 'ann':
                    out['ann_sum'] = np.array([float(v.sum())])
                else:
                    out['dg_' + k] = v[err].cpu().numpy()
        info.update(seconds=dt, batch=B, m=m, bi=bi, host=HOST, worker=a.worker, gpu=torch.cuda.get_device_name(0),
                    t_end=time.time())
        out['info'] = np.array(json.dumps(info))
        tmp = os.path.join(d, '.tmp_b%05d.npz' % bi)
        np.savez(tmp, **out)
        os.rename(tmp, os.path.join(d, 'b%05d.npz' % bi))
        nb += 1; n += m; ve += int(err.numel()); be += int(bev.sum()); sec += dt
    res = dict(set=j['set'], shape=shape, method=method, snr=snr, seed=seed, uses=n, bits=n * bpu, vec_err=ve, bit_err=be,
               ber=be / (n * bpu), seconds=sec, batches=nb, capped=n >= max_uses, host=HOST, t=time.time())
    with open(os.path.join(d, 'done.json'), 'w') as f:
        json.dump(res, f)
    log('DONE', json.dumps(res))


tuned = plan.get('tuned', {})
if 'tuned_file' in plan and os.path.exists(plan['tuned_file']):
    tuned.update(json.load(open(plan['tuned_file'])))
ctx = apx.Ctx(tuned)
filt = [x for x in a.filter.split(',') if x]
done_jobs = 0
for j in plan['jobs']:
    cpu = j['method'].startswith(CPU_METHODS)
    if (a.cpu_jobs == 'only' and not cpu) or (a.cpu_jobs == 'no' and cpu):
        continue
    jid = '%s/%s/%s/%.2f' % (j['set'], j['shape'], j['method'], j['snr'])
    if filt and not any(f in jid for f in filt):
        continue
    if j.get('needs_tuned') and j['needs_tuned'] not in ctx.tuned:
        continue
    if not claim(j):
        continue
    log('START', jid)
    try:
        run_job(j, ctx)
    except Exception as e:                                                # keep the failure, release the claim
        import traceback
        traceback.print_exc()
        d = job_dir(j)
        with open(os.path.join(d, 'failed.%d.json' % int(time.time())), 'w') as f:
            json.dump(dict(error=repr(e), worker=a.worker, host=HOST), f)
        os.rename(os.path.join(d, 'claim.json'), os.path.join(d, 'claim.failed.%d' % int(time.time())))
        torch.cuda.empty_cache()
        continue
    done_jobs += 1
    if done_jobs >= a.max_jobs:
        break
log('NO_MORE_JOBS')
