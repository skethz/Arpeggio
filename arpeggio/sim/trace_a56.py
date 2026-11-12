#!/usr/bin/env python3
"""A5.6 worker (exploratory; PROTOCOL_A56.md). Pulls jobs from a plan with exclusive claim files, as src/runner.py does, and runs
each batch by batch through a56lib.mdi_trace with the runner's draws and solver seeds, so the output is what the runner would give.
Stopping rule as PROTOCOL 3.4 unless the job fixes n_batches. A job with 'saved' must reproduce that directory's bit errors and
erroneous x_hat exactly, batch by batch; a mismatch fails the batch and is logged. Nothing is ever overwritten.
Usage: trace_a56.py --plan PLAN.json --root RESULTS_DIR --worker NAME [--threads 2] [--mem 0.20]"""
import argparse
import json
import os
import socket
import time

import numpy as np
import torch

ap = argparse.ArgumentParser()
ap.add_argument('--plan', required=True)
ap.add_argument('--root', required=True)
ap.add_argument('--worker', required=True)
ap.add_argument('--threads', type=int, default=2)
ap.add_argument('--mem', type=float, default=0.20)
a = ap.parse_args()
torch.set_num_threads(a.threads)
torch.cuda.set_per_process_memory_fraction(a.mem, 0)

import apx  # noqa: E402
import a56lib as L  # noqa: E402

HOST = socket.gethostname().split('.')[0]
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
    if sum(f.startswith('failed.') for f in os.listdir(d)) >= 3:
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
            if c.get('host') == HOST and not pid_alive(int(c.get('pid', -1))):
                os.rename(cf, cf + '.stale.%d' % int(time.time()))
                continue
            return False
    return False


def bits_per_use(shape):
    s = apx.SHAPES[shape]
    return 2 * s['nt'] * (1 if s['M'] == 4 else 2)


def tally(d):
    files = sorted(f for f in os.listdir(d) if f.startswith('b') and f.endswith('.npz'))
    n = ve = be = 0
    for f in files:
        z = np.load(os.path.join(d, f), allow_pickle=False)
        x = z['biterr']
        n += len(x); ve += int((x > 0).sum()); be += int(x.sum())
    return len(files), n, ve, be


def run_batch(j, bi, m, ctx):
    """One batch; returns the arrays to save. Used by the worker and by test_a56.py."""
    shape, method, snr, seed = j['shape'], j['method'], float(j['snr']), int(j['seed'])
    s = apx.SHAPES[shape]
    c = s['mdi']
    Rmax = int(j.get('Rmax', c['Rmax']))
    B = int(j['batch'])
    b = apx.draw(seed, snr, bi, B, s['nt'], s['M'])
    if m < B:
        for k in ('H', 'y', 'l'):
            b[k] = b[k][:m].contiguous()
    stream = j.get('stream', method)
    gs = torch.Generator(device='cuda'); gs.manual_seed(apx.draw_seed(seed, snr, bi) + 7919 + L.mhash(stream))
    z, Ai, _ = apx.mimo.mmse(b)
    cnt = {}
    solver, tl, Ns = L.solver_for(method, shape, gs, ctx, cnt)
    t0 = time.time()
    lh, tr = L.mdi_trace(b, solver, Ns, Rmax, c['S'], guesses=c['guesses'], z_mmse=z, to_levels=tl)
    torch.cuda.synchronize()
    bev = apx.biterr_per_use(b, lh)
    err = torch.nonzero(bev > 0).flatten()
    out = dict(biterr=bev.cpu().numpy().astype(np.uint8), err_idx=err.cpu().numpy().astype(np.int32),
               xhat=lh[err].cpu().numpy().astype(np.int8), t=(tr['d'] / b['N0']).astype(np.float32),
               be=tr['be'].astype(np.uint8), ann=tr['ann'].astype(np.int32), rad=tr['rad'], win=tr['win'])
    info = dict(method=method, stream=stream, Ns=Ns, Rmax=Rmax, N0=b['N0'], Nr=s['nt'], m=m, bi=bi, cnt=cnt, host=HOST,
                worker=a.worker, seconds_untimed=time.time() - t0, gpu=torch.cuda.get_device_name(0), t_end=time.time())
    out['info'] = np.array(json.dumps(info))
    return out


def check_saved(j, bi, out):
    sv = np.load(os.path.join(j['saved'], 'b%05d.npz' % bi), allow_pickle=False)
    return np.array_equal(out['biterr'], sv['biterr']) and np.array_equal(out['xhat'], sv['xhat'])


def run_job(j, ctx):
    d = job_dir(j)
    bpu = bits_per_use(j['shape'])
    B = int(j['batch'])
    max_uses = int(j.get('max_uses', int(j.get('max_bits', 1e7)) // bpu))
    min_vec, min_bit, min_uses = int(j.get('min_vec', 100)), int(j.get('min_bit', 100)), int(j.get('min_uses', 0))
    nfix = j.get('n_batches')
    nb, n, ve, be = tally(d)
    while True:
        if nfix is not None:
            if nb >= int(nfix):
                break
        elif (ve >= min_vec and be >= min_bit and n >= min_uses) or n >= max_uses:
            break
        bi = int(j.get('first_batch', 0)) + nb                             # first_batch: continue a saved series on the same draws
        m = min(B, max_uses - n)
        out = run_batch(j, bi, m, ctx)
        if j.get('saved') and not check_saved(j, bi, out):
            raise RuntimeError('replay mismatch at batch %d of %s' % (bi, j['saved']))
        tmp = os.path.join(d, '.tmp_b%05d.npz' % bi)
        np.savez_compressed(tmp, **out)
        os.rename(tmp, os.path.join(d, 'b%05d.npz' % bi))
        nb += 1; n += m; ve += int((out['biterr'] > 0).sum()); be += int(out['biterr'].sum())
    res = dict(set=j['set'], shape=j['shape'], method=j['method'], snr=float(j['snr']), seed=int(j['seed']), uses=n, bits=n * bpu,
               vec_err=ve, bit_err=be, ber=be / (n * bpu) if n else None, batches=nb, capped=n >= max_uses, host=HOST, t=time.time())
    with open(os.path.join(d, 'done.json'), 'w') as f:
        json.dump(res, f)
    log('DONE', json.dumps(res))


if __name__ == '__main__':
    tuned = json.load(open('<SCRATCH>/ap_ber_20261024/results/tuned_a5.json'))
    ctx = apx.Ctx(tuned)
    while True:                                                            # the plan is read again before every job: new picks and order apply at once
        j = next((x for x in json.load(open(a.plan))['jobs'] if claim(x)), None)
        if j is None:
            break
        jid = '%s/%s/%s/%.2f' % (j['set'], j['shape'], j['method'], j['snr'])
        log('START', jid)
        try:
            run_job(j, ctx)
        except Exception as e:
            import traceback
            traceback.print_exc()
            d = job_dir(j)
            with open(os.path.join(d, 'failed.%d.json' % int(time.time())), 'w') as f:
                json.dump(dict(error=repr(e), worker=a.worker, host=HOST), f)
            os.rename(os.path.join(d, 'claim.json'), os.path.join(d, 'claim.failed.%d' % int(time.time())))
            torch.cuda.empty_cache()
            continue
    log('NO_MORE_JOBS')
