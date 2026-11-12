#!/usr/bin/env python3
"""A5.6 checks before freezing (PROTOCOL_A56.md section 11). Dev seed 1020 plus saved held-out batches, which are recomputed and
compared only. Prints ALL PASS only if every check passes."""
import json, os, sys, time
import numpy as np, torch
sys.argv = ['test_a56', '--plan', 'x', '--root', 'x', '--worker', 'test']
import importlib.util
torch.cuda.set_per_process_memory_fraction(0.25, 0)
import apx, a56lib as L
spec = importlib.util.spec_from_file_location('tr', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_a56.py'))
tr = importlib.util.module_from_spec(spec); spec.loader.exec_module(tr)
A = '<SCRATCH>/ap_ber_20261024/results'
ctx = apx.Ctx(json.load(open(A + '/tuned_a5.json')))
ok = True


def rep(name, cond, extra=''):
    global ok
    ok = ok and bool(cond)
    print(('PASS ' if cond else 'FAIL ') + name, extra, flush=True)


# 1. ape is mimo.anechoic, bit for bit
for shape, snr, K, kap in (('x16', 20.0, 1, 0.0), ('x16', 20.0, 2, 0.0), ('x32', 22.0, 1, 0.0), ('x16', 20.0, 1, 0.3), ('q32', 14.0, 1, 0.0)):
    s = apx.SHAPES[shape]
    b = apx.draw(1020, snr, 0, 40, s['nt'], s['M'])
    z, _, _ = apx.mimo.mmse(b)
    lm = apx.mimo.quantize_levels(z / apx.mimo._mu(b, z), s['M'])
    I = apx.mimo.ising_delta_at(b, lm, K)
    S = 64 * K
    g1 = torch.Generator(device='cuda'); g1.manual_seed(5)
    g2 = torch.Generator(device='cuda'); g2.manual_seed(5)
    r1 = apx.mimo.anechoic(I, 6, S, 0.3, 0.3, 0.4, kappa=kap, gen=g1, phases=2 * K)
    c = {}
    r2 = L.ape(I, 6, S, 0.3, 0.3, 0.4, kap, 2 * K, 'alt', g2, c)
    rep('ape == mimo.anechoic %s K=%d kappa=%g' % (shape, K, kap), torch.equal(r1, r2), 'phi %.3f' % (c['flips'] / c['steps']))

# 2. mdi_trace is apx.mdi_diag: same output and same random numbers; checkpoints consistent
for shape, snr, Ns, B, meth in (('x16', 20.0, 32, 200, 'mdiane32'), ('x32', 22.0, 8, 100, 'mdiane8'), ('q32', 14.0, 8, 400, 'mdiane8')):
    s = apx.SHAPES[shape]; c = s['mdi']
    b = apx.draw(1020, snr, 3, B, s['nt'], s['M'])
    z, _, _ = apx.mimo.mmse(b)
    g1 = torch.Generator(device='cuda'); g1.manual_seed(99)
    g2 = torch.Generator(device='cuda'); g2.manual_seed(99)
    f1, tl, _ = apx.mdi_solver_for(meth, shape, g1, ctx)
    st = {}
    lh1, dg = apx.mdi_diag(b, f1, Ns, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z, stats=st, to_levels=tl)
    f2 = lambda I, na, K: L.ape(I, na, 128 * 2 * K, 0.3, 0.3, 0.4, 0.0, 2 * K, 'alt', g2)
    lh2, trc = L.mdi_trace(b, f2, Ns, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z)
    rep('mdi_trace output == mdi_diag %s' % shape, torch.equal(lh1, lh2))
    rep('same generator state after %s' % shape, torch.equal(g1.get_state(), g2.get_state()))
    rep('anneal count == mdi_diag %s' % shape, int(trc['ann'].sum()) == int(st['anneals']), 'anneals/use %.1f of %d' % (trc['ann'].sum() / B, Ns * c['S']))
    bev = apx.biterr_per_use(b, lh2).cpu().numpy()
    rep('last checkpoint == output %s' % shape, np.array_equal(trc['be'][:, -1], bev))
    # d never rises across stages: each guess keeps its best
    rep('residual never rises %s' % shape, bool((np.diff(trc['d'], axis=1) <= 1e-3).all()))
    ng = apx.mimo.mmse_sic(b, per='real') if 'sic' in c['guesses'] else None
    cands = [apx.mimo.quantize_levels(z / apx.mimo._mu(b, z), s['M'])] + ([ng] if ng is not None else [])
    dd = torch.stack([apx.dist_of(dict(H=b['H'].double(), y=b['y'].double()), x.double()) for x in cands], 1).amin(1).cpu().numpy()
    rep('checkpoint 0 is the start %s' % shape, np.allclose(trc['d'][:, 0], dd, rtol=1e-3))
    tn = trc['d'] / b['N0']
    print('   t at checkpoint 0: mean %.2f; Nr %d; R>=1 share of stage 1 %.3f' % (tn[:, 0].mean(), s['nt'], (trc['rad'][:, :, 0].sum(1) > 0).mean()), flush=True)

# 3. replay of saved held-out batches through the worker's own path
for shape, method, stream, snr, B, sub, nb, m_last in (
        ('x16', 'a56_128_0.3_0.3_0.4_0_alt_32', 'mdiane32', 20.0, 2000, 'abl/x16/mdiane32/snr_20.00', 2, None),
        ('x32', 'a56_128_0.3_0.3_0.4_0_alt_8', 'mdiane8', 22.0, 1000, 'abl/x32/mdiane8/snr_22.00', 2, None),
        ('q32', 'a56_128_0.3_0.3_0.4_0_alt_8', 'mdiane8', 14.0, 4000, 'abl/q32/mdiane8/snr_14.00', 2, None),
        ('x16', 'abl_sa_32', 'abl_sa_32', 20.0, 2000, 'abl/x16/abl_sa_32/snr_20.00', 1, None),
        ('x16', 'mdiahc32', 'mdiahc32', 20.0, 2000, 'abl/x16/mdiahc32/snr_20.00', 1, None),
        ('x32', 'mdiahc8', 'mdiahc8', 22.0, 1000, 'abl/x32/mdiahc8/snr_22.00', 1, None),
        ('x16', 'a56_128_0.3_0.3_0.4_0_alt_64', 'mdiane64', 20.0, 2000, 'tab2/x16/mdiane64/snr_20.00', 1, None)):
    seed = json.load(open(os.path.join(A, sub, 'done.json')))['seed']
    j = dict(set='test', shape=shape, method=method, stream=stream, snr=snr, seed=seed, batch=B, saved=os.path.join(A, sub))
    for bi in range(nb):
        t0 = time.time()
        out = tr.run_batch(j, bi, B, ctx)
        rep('replay %s batch %d' % (sub, bi), tr.check_saved(j, bi, out), '%.1f s, peak %.1f GB' % (time.time() - t0, torch.cuda.max_memory_allocated() / 2**30))

# 4. lane mask: exactly one active copy per coordinate, and flips only there
g = torch.Generator(device='cuda'); g.manual_seed(1)
m = L.lane_mask(3, 2, 8, 4, g, 'cuda')
rep('lane mask: one active copy per coordinate', bool((m.reshape(3, 2, 4, 8).sum(2) == 1).all()))
rep('lane mask: activity 1/P', abs(float(m.float().mean()) - 0.25) < 1e-6)
s = apx.SHAPES['x16']
b = apx.draw(1020, 20.0, 1, 20, s['nt'], s['M'])
z, _, _ = apx.mimo.mmse(b)
lm = apx.mimo.quantize_levels(z / apx.mimo._mu(b, z), s['M'])
I = apx.mimo.ising_delta_at(b, lm, 2)
g = torch.Generator(device='cuda'); g.manual_seed(2)
c = {}
out = L.ape(I, 4, 64, 0.3, 0.3, 0.4, 0.0, 4, 'lane', g, c)
rep('lane arm returns spins', bool((out.abs() == 1).all()), 'phi %.3f' % (c['flips'] / c['steps']))

# 5. stop_eval on a small hand case
t = np.array([[1.0, 1.0, 1.0], [9.0, 2.0, 2.0], [9.0, 9.0, 9.0]])
be = np.array([[3, 3, 3], [8, 1, 0], [7, 6, 5]])
ann = np.ones((3, 2, 2), dtype=np.int32)
ann[:, :, 1] = 0
b1, c1, f1 = L.stop_eval(t, be, ann, 2.5, [10.0, 20.0])
rep('stop_eval', np.array_equal(b1, [3, 1, 5]) and np.array_equal(c1, [0.0, 10.0, 20.0]) and np.array_equal(f1, [0, 1, 2]))

# 6. flip count agrees with the A5.4 calibration on its own batch
fl = json.load(open(A + '/a54/flips.json'))
s = apx.SHAPES['x16']; c0 = s['mdi']
b = apx.draw(1000, 20.0, 50, 500, s['nt'], s['M'])
g = torch.Generator(device='cuda'); g.manual_seed(1000)
cnt = {}
f = lambda I, na, K: L.ape(I, na, 128 * 2 * K, 0.3, 0.3, 0.4, 0.0, 2 * K, 'alt', g, cnt.setdefault(str(K), {}))
L.mdi_trace(b, f, 32, c0['Rmax'], c0['S'], guesses=c0['guesses'])
F1 = cnt['1']['flips'] / cnt['1']['anneals']
rep('flips per anneal at K=1 within 5%% of A5.4 (%.1f vs %.1f)' % (F1, fl['x16/128']['1']['F']), abs(F1 / fl['x16/128']['1']['F'] - 1) < 0.05)

# 7. largest arms fit in the memory cap, one full batch each
for shape, snr, B, Sk, Ns in (('x16', 20.0, 2000, 16, 256), ('x16', 20.0, 2000, 32, 256), ('x32', 22.0, 1000, 16, 64), ('x32', 22.0, 1000, 512, 2)):
    torch.cuda.reset_peak_memory_stats()
    j = dict(set='test', shape=shape, method='a56_%d_0.3_0.3_0.4_0_alt_%d' % (Sk, Ns), snr=snr, seed=1020, batch=B)
    t0 = time.time()
    out = tr.run_batch(j, 0, B, ctx)
    print('   arm %s: %.1f s, peak %.2f GB, anneals/use %.1f, err uses %d' % (j['method'], time.time() - t0, torch.cuda.max_memory_allocated() / 2**30, out['ann'].sum() / B, (out['biterr'] > 0).sum()), flush=True)
print('ALL PASS' if ok else 'FAIL', flush=True)
