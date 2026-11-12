#!/usr/bin/env python3
"""A5.4 shared-GPU replay: recompute saved batches of Antiphase (i) at P1 and P2 (held-out seed 102, already reported) with the
runner's own seeds, on a GPU that another user's job is sharing, and compare every saved array bit by bit.
Usage: replay_a54.py N_BATCHES"""
import hashlib, os, sys, time, json, numpy as np, torch, apx, runner_a54  # noqa: F401
A = '<SCRATCH>/ap_ber_20261024/results/abl'
N = int(sys.argv[1]); ctx = apx.Ctx({})
mh = lambda m: int(hashlib.sha256(m.encode()).hexdigest()[:8], 16) % 1_000_000
name = torch.cuda.get_device_name(0); uuid = os.environ.get('MIMO_GPU_UUID', '')[:12]
bad = 0
for shape, m, snr, B in (('x16', 'mdiane32', 20.0, 2000), ('x32', 'mdiane8', 22.0, 1000)):
    s = apx.SHAPES[shape]
    for bi in range(N):
        b = apx.draw(102, snr, bi, B, s['nt'], s['M'])
        gs = torch.Generator(device='cuda'); gs.manual_seed(apx.draw_seed(102, snr, bi) + 7919 + mh(m))
        t0 = time.time()
        z, _, _ = apx.mimo.mmse(b)
        lh, _, _ = apx.detect(m, b, shape, gs, ctx, z=z)
        torch.cuda.synchronize(); dt = time.time() - t0
        bev = apx.biterr_per_use(b, lh).cpu().numpy().astype(np.uint8)
        err = np.nonzero(bev)[0]
        sv = np.load('%s/%s/%s/snr_%05.2f/b%05d.npz' % (A, shape, m, snr, bi), allow_pickle=False)
        same = np.array_equal(bev, sv['biterr']) and np.array_equal(lh.cpu().numpy()[err].astype(np.int8), sv['xhat'])
        bad += (not same)
        print(uuid, shape, 'batch', bi, 'identical' if same else 'DIFFERENT', 'saved bit errors', int(sv['biterr'].sum()), 'now', int(bev.sum()),
              '%.1f s (saved %.1f s)' % (dt, json.loads(str(sv['info']))['seconds']), 'peak %.1f GB' % (torch.cuda.max_memory_allocated() / 2**30), flush=True)
print(uuid, name, 'ALL IDENTICAL' if bad == 0 else 'MISMATCH %d' % bad, flush=True)
