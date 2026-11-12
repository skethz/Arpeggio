#!/usr/bin/env python3
"""A5.17 S2 (PROTOCOL_A517.md section 5): per-round commit counters for Chord's three kernels, on the exact calibration runs
that define the printed reference costs. Counter-only source patches; gates G1-G3 run first and abort on any failure.
Usage: s2_counts.py OUT.json   (run from <SCRATCH>/ap_ber_20261024/a517 with ../src on sys.path)"""
import glob, inspect, json, os, sys, textwrap, time
SRC = '<SCRATCH>/ap_ber_20261024/src'
sys.path.insert(0, SRC)
import numpy as np, torch  # noqa: E402
import apx, apx55, a56lib, runner_a55  # noqa: E402,F401
import mdi_solvers  # noqa: E402
_c = mdi_solvers.MDI[('64x64', 16)]                                       # x64 registration exactly as trace_x64.py (A5.8)
apx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(_c['Rmax']), S=int(_c['S']), guesses=tuple(_c['guesses'])), Ns_pub=None))
OUT = sys.argv[1]
if os.path.exists(OUT):
    sys.exit('refusing: exists')
torch.set_num_threads(1)
RES = '<SCRATCH>/ap_ber_20261024/results'
KEYS = ('c1', 'c2', 'c4', 'cinf', 'rounds', 'h0', 'h1', 'h2', 'h3', 'h4p')


def _a517_round(m, d, K):
    """m: (B, R) flips in this round. d: count dict; K None -> d is already the per-K dict (a56lib)."""
    if d is None:
        return
    t = d.setdefault('_a517', {}) if K is None else d.setdefault('_a517', {}).setdefault(str(K), {})
    m = m.to(torch.int64)
    v = torch.stack([m.sum(), ((m + 1) // 2).sum(), ((m + 3) // 4).sum(), (m > 0).sum(), torch.tensor(m.numel(), device=m.device),
                     (m == 0).sum(), (m == 1).sum(), (m == 2).sum(), (m == 3).sum(), (m >= 4).sum()]).tolist()
    for k, x in zip(KEYS, v):
        t[k] = t.get(k, 0) + int(x)


def patched(mod, fname, anchor, new):
    src = textwrap.dedent(inspect.getsource(getattr(mod, fname)))
    assert src.count(anchor) == 1, (fname, src.count(anchor))
    ns = dict(vars(mod))
    ns['_a517_round'] = _a517_round
    exec(compile(src.replace(anchor, new), '<a517 %s>' % fname, 'exec'), ns)
    return ns[fname]


A_CL = '        ds = torch.where(z < rr, -2 * ss, torch.zeros_like(ss))\n'
P_CL = patched(apx, 'anechoic_classes', A_CL, A_CL + "        _a517_round((ds != 0).sum(-1), count, count.get('_K') if count is not None else None)\n")
A_AK = '        flip = (z < rr) & (idx == (k % P))\n'
P_AK = patched(apx55, 'ape_k', A_AK, A_AK + '        _a517_round(flip.sum(-1), count, P // 2)\n')
A_56 = '        sprev = s\n        s = torch.where(flip, -s, s)\n'
P_56 = patched(a56lib, 'ape', A_56, '        _a517_round(flip.sum(-1), cnt, None)\n' + A_56)
ORIG = dict(cl=apx.anechoic_classes, ak=apx55.ape_k, a56=a56lib.ape)
import hashlib  # noqa: E402
log = dict(protocol_sha256=hashlib.sha256(open('<SCRATCH>/ap_ber_20261024/a517/PROTOCOL_A517.md', 'rb').read()).hexdigest(),
           script_sha256=hashlib.sha256(open(os.path.abspath(__file__), 'rb').read()).hexdigest(), gates={}, runs={})


def save():
    with open(OUT + '.tmp', 'w') as f:
        json.dump(log, f, indent=1)
    os.replace(OUT + '.tmp', OUT)


# ---- G1/G3: bit-identical best_s and identical generator state, on synthetic instances ----
def inst(B, N, dev='cuda', seed=5):
    g = torch.Generator(device=dev); g.manual_seed(seed)
    A = torch.randn(B, N, N, generator=g, device=dev)
    J = -(A + A.transpose(1, 2)) / 8
    J = J - torch.diag_embed(torch.diagonal(J, dim1=1, dim2=2))
    return dict(h=torch.randn(B, N, generator=g, device=dev), J=J, h0=torch.randn(B, N, generator=g, device=dev))


def same(fa, fb, args_a, args_b):
    ga = torch.Generator(device='cuda'); ga.manual_seed(77)
    gb = torch.Generator(device='cuda'); gb.manual_seed(77)
    a = fa(*args_a(ga)); b = fb(*args_b(gb))
    return bool(torch.equal(a, b)) and bool(torch.equal(ga.get_state(), gb.get_state()))


g1 = {}
for P in (2, 4, 6):
    I = inst(3, 16 * P)
    cl = apx.colour_classes(16 * P, P, 'copy', 1, 'cuda')
    c0, c1 = {'_K': P // 2}, {'_K': P // 2}
    g1['cl_P%d' % P] = same(ORIG['cl'], P_CL, lambda g: (I, 4, 0.3, 0.4, cl, 8, g, c0), lambda g: (I, 4, 0.3, 0.4, cl, 8, g, c1)) and \
        c0[P // 2]['flips'] == c1['_a517'][str(P // 2)]['c1']
    k0, k1 = {}, {}
    g1['ak_P%d' % P] = same(ORIG['ak'], P_AK, lambda g: (I, 4, 8 * P, 0.2, 0.2, 0.2, P, 'rand', g, k0),
                            lambda g: (I, 4, 8 * P, 0.2, 0.2, 0.2, P, 'rand', g, k1)) and k0[P // 2]['flips'] == k1['_a517'][str(P // 2)]['c1']
    a0, a1 = {}, {}
    g1['a56_P%d' % P] = same(ORIG['a56'], P_56, lambda g: (I, 4, 8 * P, 0.3, 0.3, 0.4, 0.0, P, 'alt', g, a0),
                             lambda g: (I, 4, 8 * P, 0.3, 0.3, 0.4, 0.0, P, 'alt', g, a1)) and a0['flips'] == a1['_a517']['c1']
log['gates']['G1_G3'] = g1
save()
print('G1/G3', g1, flush=True)
if not all(g1.values()):
    sys.exit('GATE G1/G3 FAILED')
apx.anechoic_classes, apx55.ape_k, a56lib.ape = P_CL, P_AK, P_56


def per_k(cnt_flat):
    """cnt_flat: K -> dict(steps, anneals, _a517 counters). Returns per-anneal L, F and c_k, plus histogram fractions."""
    out = {}
    for K, v in cnt_flat.items():
        a, n = v['_a517'], v['anneals']
        out[K] = dict(L=v['steps'] / n, F=v['flips'] / n, **{k: a[k] / n for k in ('c1', 'c2', 'c4', 'cinf')},
                      frac={k: a[k] / a['rounds'] for k in ('h0', 'h1', 'h2', 'h3', 'h4p')}, raw=dict(v))
    return out


# ---- R1: calib_flips.py exactly (x16, x32, q32) -> G2 vs a5_flip_phi raw ----
ref = json.load(open(RES + '/a5_flip_phi.json'))['raw']
for shape, snr, Ns, B, nb in (('x16', 20.0, 32, 2000, 1), ('x32', 22.0, 8, 1000, 1), ('q32', 14.0, 8, 4000, 1)):
    t0 = time.time()
    s = apx.SHAPES[shape]
    cnt = {}
    for bi in range(nb):
        b = apx.draw(1000, snr, 50 + bi, B, s['nt'], s['M'])
        gs = torch.Generator(device='cuda'); gs.manual_seed(1000 + bi)
        solver = lambda I, na, K: apx.anechoic_colour(I, na, 0.3, 0.4, 2 * K, 1, gen=gs, count=cnt)  # noqa: E731
        c = s['mdi']
        apx.mdi_diag(b, solver, Ns, c['Rmax'], c['S'], guesses=c['guesses'])
    flat = {}
    for K, v in cnt.items():
        if K in ('_K', '_a517'):
            continue
        flat[str(K)] = dict(v, _a517=cnt['_a517'][str(K)])
    g2 = all(flat[K]['flips'] == ref[shape][K]['flips'] and flat[K]['steps'] == ref[shape][K]['steps'] and
             flat[K]['anneals'] == ref[shape][K]['anneals'] and flat[K]['_a517']['c1'] == flat[K]['flips'] for K in ref[shape])
    log['gates']['G2_default_' + shape] = g2
    log['runs']['default_' + shape] = per_k(flat)
    log['runs']['default_' + shape + '_seconds'] = time.time() - t0
    save()
    print(shape, 'G2', g2, {K: {k: round(v[k], 3) for k in ('L', 'F', 'c2', 'cinf')} for K, v in log['runs']['default_' + shape].items()}, flush=True)
    if not g2:
        sys.exit('GATE G2 FAILED ' + shape)

# ---- R2: re-tuned C1 calibration (calib_flips_a55.py, P2 entry) -> G2 vs a55/flips.json ----
m = 'abl_ape_0.2_0.2_0.2_rand_8'
fl = json.load(open('<SCRATCH>/ap_ber_20261024/results/a55/flips.json'))[m]
ctx = apx.Ctx(json.load(open(RES + '/tuned_a52.json')))
s = apx.SHAPES['x32']
b = apx.draw(1000, 22.0, 50, 500, s['nt'], s['M'])
gs = torch.Generator(device='cuda'); gs.manual_seed(1000)
z, _, _ = apx.mimo.mmse(b)
_, _, info = apx.detect(m, b, 'x32', gs, ctx, z=z)
cntc = info['count']
a5 = cntc.get('_a517', {})
flat = {str(K): dict(v, _a517=a5[str(K)]) for K, v in cntc.items() if K != '_a517'}
g2 = all(flat[K]['flips'] == fl[K]['flips'] and flat[K]['steps'] == fl[K]['steps'] and flat[K]['anneals'] == fl[K]['anneals']
         and flat[K]['_a517']['c1'] == flat[K]['flips'] for K in fl)
log['gates']['G2_retuned_C1'] = g2
log['runs']['retuned_C1_x32'] = per_k(flat)
save()
print('C1 G2', g2, flush=True)
if not g2:
    sys.exit('GATE G2 FAILED C1')

# ---- R3: A5.8 tunea REF (x64, seed 1000, batches 0-7 of 500) -> G2 vs the stored batch counters ----
REFM, STREAM = 'a56_128_0.3_0.3_0.4_0_alt_8', 'mdiane8'
D = RES + '/a58/tunea/x64/' + REFM + '/snr_22.00'
tot, g2 = {}, True
s = apx.SHAPES['x64']
c = s['mdi']
for f in sorted(glob.glob(D + '/b*.npz')):
    st = json.loads(str(np.load(f, allow_pickle=False)['info']))
    bi, mm = int(st['bi']), int(st['m'])
    b = apx.draw(1000, 22.0, bi, 500, s['nt'], s['M'])
    if mm < 500:
        for k in ('H', 'y', 'l'):
            b[k] = b[k][:mm].contiguous()
    gs = torch.Generator(device='cuda'); gs.manual_seed(apx.draw_seed(1000, 22.0, bi) + 7919 + a56lib.mhash(STREAM))
    z, _, _ = apx.mimo.mmse(b)
    cnt = {}
    solver, tl, Ns = a56lib.solver_for(REFM, 'x64', gs, ctx, cnt)
    a56lib.mdi_trace(b, solver, Ns, int(st['Rmax']), c['S'], guesses=c['guesses'], z_mmse=z, to_levels=tl)
    for K, v in cnt.items():
        ok = v['flips'] == st['cnt'][K]['flips'] and v['steps'] == st['cnt'][K]['steps'] and v['anneals'] == st['cnt'][K]['anneals'] \
            and v['_a517']['c1'] == v['flips']
        g2 = g2 and ok
        t = tot.setdefault(K, dict(flips=0.0, steps=0.0, anneals=0.0, _a517={k: 0 for k in KEYS}))
        for k in ('flips', 'steps', 'anneals'):
            t[k] += v[k]
        for k in KEYS:
            t['_a517'][k] += v['_a517'][k]
    print('x64 batch', bi, 'match', g2, flush=True)
rc = {K: 256 * int(K) + v['flips'] / v['anneals'] for K, v in tot.items()}
sel = json.load(open(RES + '/a58/select.json'))['ref_cost']
g2 = g2 and all(abs(rc[K] - sel[K]) < 1e-9 for K in sel)
log['gates']['G2_x64'] = g2
log['runs']['default_x64'] = per_k(tot)
save()
print('x64 G2', g2, flush=True)
if not g2:
    sys.exit('GATE G2 FAILED x64')
log['done'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
save()
print('A5.17 S2 DONE', flush=True)
