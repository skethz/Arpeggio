#!/usr/bin/env python3
"""A5.5 replay (PROTOCOL_A55.md section 12): with fa_seq in place of sa_seq, recompute saved batches of sequential SA (held-out
seed 102, already reported) with the runner's own seeds, and compare every saved array bit by bit. Usage: replay_a55.py"""
import hashlib, json, os, time, numpy as np, torch, apx, apx55, runner_a55  # noqa: F401
A = '<SCRATCH>/ap_ber_20261024/results/abl'
ctx = apx.Ctx(json.load(open('<SCRATCH>/ap_ber_20261024/results/tuned_a52.json')))
mh = lambda m: int(hashlib.sha256(m.encode()).hexdigest()[:8], 16) % 1_000_000
apx.sa_seq = lambda I, R, sweeps, T0, T1, K, gen=None, count=None: apx55.fa_seq(I, R, sweeps, T0, T1, K, rule='m', start='rand', gen=gen, count=count)
uuid = os.environ.get('MIMO_GPU_UUID', '')[:12]
bad = 0
for shape, m, snr, B in (('x16', 'abl_sao_8_32', 20.0, 2000), ('x32', 'abl_sas_8_8', 22.0, 1000), ('x16', 'abl_sao_2_32', 20.0, 2000), ('x32', 'abl_sas_2_8', 22.0, 1000)):
    s = apx.SHAPES[shape]
    b = apx.draw(102, snr, 0, B, s['nt'], s['M'])
    gs = torch.Generator(device='cuda'); gs.manual_seed(apx.draw_seed(102, snr, 0) + 7919 + mh(m))
    t0 = time.time()
    z, _, _ = apx.mimo.mmse(b)
    lh, _, _ = apx.detect(m, b, shape, gs, ctx, z=z)
    torch.cuda.synchronize(); dt = time.time() - t0
    bev = apx.biterr_per_use(b, lh).cpu().numpy().astype(np.uint8)
    err = np.nonzero(bev)[0]
    sv = np.load('%s/%s/%s/snr_%05.2f/b00000.npz' % (A, shape, m, snr), allow_pickle=False)
    same = np.array_equal(bev, sv['biterr']) and np.array_equal(lh.cpu().numpy()[err].astype(np.int8), sv['xhat'])
    bad += (not same)
    print(uuid, shape, m, 'identical' if same else 'DIFFERENT', 'saved bit errors', int(sv['biterr'].sum()), 'now', int(bev.sum()),
          '%.1f s (saved %.1f s)' % (dt, json.loads(str(sv['info']))['seconds']), 'peak %.1f GB' % (torch.cuda.max_memory_allocated() / 2**30), flush=True)
print(uuid, 'ALL IDENTICAL' if bad == 0 else 'MISMATCH %d' % bad, flush=True)
