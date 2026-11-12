#!/usr/bin/env python3
"""A5.13 gates (PROTOCOL_A513.md section 4). No held-out draw is read except the saved X3P batches named in G2.
  g1 OUT.json   G1a: fa_fx.cu against fa_ref59.anneal (the A5.9 file, unchanged; its bottom command block is not run) on A5.5/A5.9's
                captured sub-problems (P1 D = 32, P2 D = 64), K = 1-3, two keys, both starts, two schedules.
                G1b: on real sub-problems recorded through run_a513.detect on dev seed 9600 at x16, x32 and x64 (D = 32, 64, 128),
                with the keys and instance numbers of the run itself.
                Compared per anneal: best energy change, best spins, flips, comparator passes. Any mismatch fails.
  g2 RUNDIR REFS.npz SET OUT.json   G2 (host check): run_a513 --solver prod against X3P's saved per-use bit errors (hostB), batch by batch.
  g2b RUNDIR ORIGDIR OUT.json       G2 (driver check): run_a513 --solver prod against the unchanged x3_prod.py run on the same host:
                                    identical per-use bit errors and erroneous x_hat. Any difference fails."""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np

REF = os.path.join(HERE, 'fa_ref59.py')
CAPS = {'P1': os.path.join(HERE, '..', 'refs', 'capture_9600.pt'), 'P2': os.path.join(HERE, '..', 'refs', 'capture_p2_9600.pt')}
A59_SEED = 0x1234567890ABCDEF


def load_ref():
    src = open(REF).read()
    cut = src.index("\nif sys.argv[1] == 'gen':")
    ns = {'__name__': 'fa_ref59'}
    exec(compile(src[:cut], REF, 'exec'), ns)
    return ns


def bits(sp, P, D):
    return [''.join('1' if sp[p * D + j] > 0 else '0' for j in reversed(range(D))) for p in range(P)]


def check(ns, G, h, P, T, q, inst, key, start, spins, de, st, rs):
    """Reference anneals r in rs of every sub-problem b; returns (anneals compared, failures, details of the first failures)."""
    ns['SEED'] = key
    n = bad = 0
    det = []
    B, D = h.shape
    for b in range(B):
        Gl, hl = [[int(v) for v in row] for row in G[b]], [int(v) for v in h[b]]
        for r in rs:
            ref = ns['anneal'](Gl, hl, P, T, q, r, int(inst[b]), start, 'fa')
            got = dict(best=int(de[b, r]), bs=bits(spins[b, r], P, D), flips=int(st[b, r, 0]), tests=int(st[b, r, 1]))
            want = dict(best=ref['best'], bs=ref['bs'], flips=len(ref['acc']), tests=sum(ref['tests']))
            n += 1
            if got != want:
                bad += 1
                if len(det) < 5:
                    det.append(dict(b=b, r=r, got={k: v for k, v in got.items() if k != 'bs'}, want={k: v for k, v in want.items() if k != 'bs'},
                                    spins_equal=got['bs'] == want['bs']))
    return n, bad, det


def g1(out):
    import torch
    import anefx
    import mimo
    import fafx
    import run_a513
    torch.set_num_threads(4)
    ns = load_ref()
    res = dict(g1a={}, g1b={})
    rnd = random.Random(513)
    Q = anefx.QSCALE
    picks = {'P1': 'abl_far_64_0.1_0.1_0_rand_32', 'P2': 'abl_far_32_0.1_0.1_0_rand_8'}
    tot_n = tot_bad = 0
    for cap, path in CAPS.items():
        Dc = torch.load(path)
        pk = run_a513.parse_pick(picks[cap])
        sch = {'pick': (pk['S'], pk['T0'], pk['T1'], pk['q']), 'a59hot': (8, 1.2, 0.1, 0.2)}
        for K in (1, 2, 3):
            G, h = Dc[K]['G'][:6].long(), Dc[K]['h'][:6].long()
            P = 2 * K
            for sname, (S, T0, T1, q) in sch.items():
                Tsw = [int(round(v * Q)) for v in mimo.geom(T0, T1, S, 'cpu').double().tolist()]
                T = [t for t in Tsw for _ in range(P)]
                qi = int(round(q * Q))
                for key in (A59_SEED, rnd.getrandbits(64)):
                    for start in ('rand', 'bal'):
                        inst = np.array([1000 * K + b for b in range(G.shape[0])], dtype=np.int64)
                        t0 = time.time()
                        spins, de, st = fafx.solve(G, h, P, 2, T, qi, inst, key, start)
                        n, bad, det = check(ns, G.numpy(), h.numpy(), P, T, qi, inst, key, start, spins, de, st, (0, 1))
                        k = '%s/K%d/%s/%s/%x' % (cap, K, sname, start, key)
                        res['g1a'][k] = dict(anneals=n, failed=bad, flips=int(st[..., 0].sum()), sec=round(time.time() - t0, 1), first=det)
                        tot_n += n; tot_bad += bad
                        print('G1a', k, n, 'anneals', bad, 'failed', int(st[..., 0].sum()), 'flips', flush=True)
    shapes = {'x16': (16, 20.0, 'abl_far_64_0.1_0.1_0_rand_32'), 'x32': (32, 22.0, 'abl_far_32_0.1_0.1_0_rand_8'),
              'x64': (64, 22.0, 'abl_far_64_0.1_0.1_0_bal_8')}
    import apx
    for tag, (nt, snr, pick) in shapes.items():
        rec = []
        b = apx.draw(9600, snr, 0, 40, nt, 16, dev='cpu')
        pk = run_a513.parse_pick(pick)
        run_a513.detect(b, nt, 16, apx.draw_seed(9600, snr, 0), pk, 'fafx', 4, hook=rec.append)
        seenK = {}
        for c in rec:
            K = c['P'] // 2
            if seenK.get(K, 0) >= 2:
                continue
            seenK[K] = seenK.get(K, 0) + 1
            nb = min(3, c['G'].shape[0])
            rs = tuple(range(min(2, c['R'])))
            t0 = time.time()
            n, bad, det = check(ns, c['G'][:nb].numpy(), c['h'][:nb].numpy(), c['P'], c['T'], c['q'], c['inst'][:nb], c['key'], c['start'],
                                c['spins'][:nb], c['de'][:nb], c['st'][:nb], rs)
            k = '%s/K%d/call%d' % (tag, K, seenK[K])
            res['g1b'][k] = dict(anneals=n, failed=bad, D=int(c['G'].shape[1]), R=c['R'], key='%x' % c['key'], sec=round(time.time() - t0, 1), first=det)
            tot_n += n; tot_bad += bad
            print('G1b', k, 'D', c['G'].shape[1], n, 'anneals', bad, 'failed', flush=True)
        res['g1b'][tag + '/calls'] = len(rec)
    res['total'] = dict(anneals=tot_n, failed=tot_bad, verdict='PASS' if tot_bad == 0 else 'FAIL')
    json.dump(res, open(out, 'w'), indent=1)
    print('G1', res['total'], flush=True)
    return tot_bad


def g2(rundir, refs, name, out):
    z = np.load(refs, allow_pickle=False)
    files = sorted(f for f in os.listdir(rundir) if f.startswith('b') and f.endswith('.npz'))
    rows, bad = [], 0
    for f in files:
        bi = int(f[1:6])
        x = np.load(os.path.join(rundir, f), allow_pickle=False)['biterr']
        y = z['%s/b%05d' % (name, bi)]
        same = bool(np.array_equal(x, y))
        bad += 0 if same else 1
        rows.append(dict(batch=bi, uses=int(len(x)), identical=same, run_bit_err=int(x.sum()), saved_bit_err=int(y.sum()),
                         uses_differing=int((x != y).sum())))
    res = dict(set=name, batches=rows, verdict='PASS' if bad == 0 and rows else 'FAIL')
    json.dump(res, open(out, 'w'), indent=1)
    print('G2', json.dumps(res), flush=True)
    return bad


def g2b(rundir, origdir, out):
    rows, bad = [], 0
    for f in sorted(f for f in os.listdir(origdir) if f.startswith('b') and f.endswith('.npz')):
        x = np.load(os.path.join(rundir, f), allow_pickle=False)
        y = np.load(os.path.join(origdir, f), allow_pickle=False)
        same = bool(np.array_equal(x['biterr'], y['biterr']) and np.array_equal(x['err_idx'], y['err_idx']) and np.array_equal(x['xhat'], y['xhat']))
        bad += 0 if same else 1
        rows.append(dict(batch=int(f[1:6]), uses=int(len(x['biterr'])), identical=same, run_bit_err=int(x['biterr'].sum()),
                         orig_bit_err=int(y['biterr'].sum())))
    res = dict(rundir=rundir, origdir=origdir, batches=rows, verdict='PASS' if bad == 0 and rows else 'FAIL')
    json.dump(res, open(out, 'w'), indent=1)
    print('G2b', json.dumps(res), flush=True)
    return bad


if __name__ == '__main__':
    if sys.argv[1] == 'g2b':
        sys.exit(1 if g2b(sys.argv[2], sys.argv[3], sys.argv[4]) else 0)
    if sys.argv[1] == 'g1':
        sys.exit(1 if g1(sys.argv[2]) else 0)
    sys.exit(1 if g2(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]) else 0)
