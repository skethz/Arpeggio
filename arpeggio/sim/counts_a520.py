#!/usr/bin/env python3
"""A5.20 S2: per-round commit counts of re-tuned Chord C64 (abl_chord_0.2_0.2_0.2_rand_8) on A5.19's
calibration batch (seed 1000, index 50, 500 uses, stream = method), through the worker's own run_batch with arpx55.chord_k replaced by
A5.17's counter-only copy (verbatim patch). Gates G1/G3 (patched kernel bit-identical, same generator state), G2 (stored calibration
batch reproduced: biterr, xhat, per-K flips/steps/anneals, c1 = flips), G2x (x_1 = stored x(C64) to 1e-9) must pass.
Usage (hostB, from a520/): counts_a520.py OUT.json STORED_B00050.npz"""
import hashlib, inspect, json, os, sys, textwrap
OUT, STORED = sys.argv[1], sys.argv[2]
if os.path.exists(OUT):
    sys.exit('refusing: exists')
SRC = '<SCRATCH>/arpeggio_ber_20261024/src'
sys.path.insert(0, SRC)
sys.argv = [os.path.join(SRC, 'trace_a56.py'), '--plan', '/dev/null', '--root', os.path.dirname(os.path.abspath(OUT)),
            '--worker', 'a520counts', '--threads', '2', '--mem', '0.20']
import numpy as np, torch  # noqa: E402
import arpx, arpx514, arpx55, mdi_solvers  # noqa: E402
_c = mdi_solvers.MDI[('64x64', 16)]                                        # registration exactly as trace_a514.py
arpx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(_c['Rmax']), S=int(_c['S']), guesses=tuple(_c['guesses'])), Ns_pub=None))
arpx514.install()
import trace_a56 as T  # noqa: E402  (module import: argparse above, no __main__ loop)

C64 = 'abl_chord_0.2_0.2_0.2_rand_8'
REF4 = {str(k): float(v) for k, v in json.load(open('<SCRATCH>/arpeggio_ber_20261024/results/a58/select.json'))['ref_cost'].items()}
X_STORED = 3.2131374620947764                                               # A5.19 select.json calib_x[C64] (hostB)
KEYS = ('c1', 'c2', 'c4', 'cinf', 'rounds', 'h0', 'h1', 'h2', 'h3', 'h4p')


def _a517_round(m, d, K):                                                    # A5.17 s2_counts.py, verbatim
    """m: (B, R) flips in this round. d: count dict; K None -> d is already the per-K dict (a56lib)."""
    if d is None:
        return
    t = d.setdefault('_a517', {}) if K is None else d.setdefault('_a517', {}).setdefault(str(K), {})
    m = m.to(torch.int64)
    v = torch.stack([m.sum(), ((m + 1) // 2).sum(), ((m + 3) // 4).sum(), (m > 0).sum(), torch.tensor(m.numel(), device=m.device),
                     (m == 0).sum(), (m == 1).sum(), (m == 2).sum(), (m == 3).sum(), (m >= 4).sum()]).tolist()
    for k, x in zip(KEYS, v):
        t[k] = t.get(k, 0) + int(x)


def patched(mod, fname, anchor, new):                                        # A5.17 s2_counts.py, verbatim
    src = textwrap.dedent(inspect.getsource(getattr(mod, fname)))
    assert src.count(anchor) == 1, (fname, src.count(anchor))
    ns = dict(vars(mod))
    ns['_a517_round'] = _a517_round
    exec(compile(src.replace(anchor, new), '<a517 %s>' % fname, 'exec'), ns)
    return ns[fname]


A_AK = '        flip = (z < rr) & (idx == (k % P))\n'
P_AK = patched(arpx55, 'chord_k', A_AK, A_AK + '        _a517_round(flip.sum(-1), count, P // 2)\n')
ORIG_AK = arpx55.chord_k
log = dict(script_sha256=hashlib.sha256(open(os.path.abspath(__file__), 'rb').read()).hexdigest(), gates={}, runs={})


def save():
    with open(OUT + '.tmp', 'w') as f:
        json.dump(log, f, indent=1)
    os.replace(OUT + '.tmp', OUT)


# ---- G1/G3 (A5.17 code for chord_k): bit-identical result and generator state on synthetic instances ----
def inst(B, N, dev='cuda', seed=5):
    g = torch.Generator(device=dev); g.manual_seed(seed)
    A = torch.randn(B, N, N, generator=g, device=dev)
    J = -(A + A.transpose(1, 2)) / 8
    J = J - torch.diag_embed(torch.diagonal(J, dim1=1, dim2=2))
    return dict(h=torch.randn(B, N, generator=g, device=dev), J=J, h0=torch.randn(B, N, generator=g, device=dev))


def same(arpeggio, fb, args_a, args_b):
    ga = torch.Generator(device='cuda'); ga.manual_seed(77)
    gb = torch.Generator(device='cuda'); gb.manual_seed(77)
    a = arpeggio(*args_a(ga)); b = fb(*args_b(gb))
    return bool(torch.equal(a, b)) and bool(torch.equal(ga.get_state(), gb.get_state()))


g1 = {}
for P in (2, 4, 6):
    I = inst(3, 16 * P)
    k0, k1 = {}, {}
    g1['ak_P%d' % P] = same(ORIG_AK, P_AK, lambda g: (I, 4, 8 * P, 0.2, 0.2, 0.2, P, 'rand', g, k0),
                            lambda g: (I, 4, 8 * P, 0.2, 0.2, 0.2, P, 'rand', g, k1)) and k0[P // 2]['flips'] == k1['_a517'][str(P // 2)]['c1']
log['gates']['G1_G3'] = g1
save()
print('G1/G3', g1, flush=True)
if not all(g1.values()):
    sys.exit('GATE G1/G3 FAILED')
arpx55.chord_k = P_AK

# ---- the C64 calibration batch through the worker's run_batch ----
ctx = arpx.Ctx(json.load(open('<SCRATCH>/arpeggio_ber_20261024/results/tuned_a5.json')))   # as trace_a56 __main__
j = dict(set='calib', shape='x64', method=C64, snr=22.0, batch=500, point='P4', seed=1000, first_batch=50, n_batches=1)
out = T.run_batch(j, 50, 500, ctx)
info = json.loads(str(out['info']))
sv = np.load(STORED, allow_pickle=False)
st = json.loads(str(sv['info']))
cnt, scnt = info['cnt']['cnt'], st['cnt']['cnt']
a5 = cnt.pop('_a517')
g2 = bool(np.array_equal(out['biterr'], sv['biterr']) and np.array_equal(out['xhat'], sv['xhat']))
g2 = g2 and st['method'] == C64 and int(st['bi']) == 50 and set(cnt) == set(scnt)
for K in scnt:
    g2 = g2 and all(cnt[K][f] == scnt[K][f] for f in ('flips', 'steps', 'anneals')) and a5[K]['c1'] == cnt[K]['flips']
per = {}
for K, v in cnt.items():
    n = v['anneals']
    per[K] = dict(L=v['steps'] / n, F=v['flips'] / n, **{k: a5[K][k] / n for k in ('c1', 'c2', 'c4', 'cinf')},
                  frac={k: a5[K][k] / a5[K]['rounds'] for k in ('h0', 'h1', 'h2', 'h3', 'h4p')}, raw=dict(v, _a517=a5[K]), ref=REF4[K])
xk = {k: float(np.mean([(p['L'] + p[k]) / p['ref'] for p in per.values()])) for k in ('c1', 'c2', 'c4', 'cinf')}
xk['free'] = float(np.mean([p['L'] / p['ref'] for p in per.values()]))
g2x = abs(xk['c1'] - X_STORED) < 1e-9
log['gates']['G2'] = g2
log['gates']['G2x'] = g2x
log['runs']['C64_calib'] = per
log['x_k'] = xk
log['stored'] = dict(file=STORED, sha256=hashlib.sha256(open(STORED, 'rb').read()).hexdigest(), host=st.get('host'))
save()
print('G2', g2, 'G2x', g2x, 'x_k', {k: round(v, 4) for k, v in xk.items()}, flush=True)
print('hist', {K: {k: round(x, 3) for k, x in p['frac'].items()} for K, p in per.items()}, flush=True)
if not (g2 and g2x):
    sys.exit('GATE G2 FAILED')
log['done'] = True
save()
print('A5.20 S2 DONE', flush=True)
