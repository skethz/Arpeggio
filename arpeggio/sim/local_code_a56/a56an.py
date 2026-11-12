#!/usr/bin/env python3
"""A5.6 analysis helpers (numpy only, no GPU; PROTOCOL_A56.md section 9). A run is one job directory of trace batches."""
import glob
import json
import math
import os

import numpy as np

C_GRID = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def load(d, nmax=None):
    """Concatenates the batches of one job directory. Returns None if there are none."""
    fs = sorted(glob.glob(os.path.join(d, 'b*.npz')))
    if nmax is not None:
        fs = fs[:nmax]
    if not fs:
        return None
    out, cnt, sizes, Nr, N0, meth = {k: [] for k in ('biterr', 't', 'be', 'ann', 'rad', 'win')}, {}, [], None, None, None
    for f in fs:
        z = np.load(f, allow_pickle=False)
        for k in out:
            out[k].append(z[k])
        info = json.loads(str(z['info']))
        sizes.append(len(z['biterr']))
        Nr, N0, meth = info['Nr'], info['N0'], info['method']
        c = info.get('cnt', {})
        c = c.get('cnt', c) if isinstance(c, dict) else {}
        for K, v in c.items():
            a = cnt.setdefault(str(K), dict(flips=0.0, anneals=0.0))
            a['flips'] += float(v.get('flips', 0.0)); a['anneals'] += float(v.get('anneals', 0.0))
    r = {k: np.concatenate(v, 0) for k, v in out.items()}
    r.update(cnt=cnt, sizes=sizes, Nr=Nr, N0=N0, method=meth)
    return r


def sk_of(method, default=128):
    a = method.split('_')
    return int(a[1]) if a[0] == 'a56' else default


def cyc_table(run, Rmax):
    """L_K + F_K per anneal, L_K = Sk 2K, F_K measured on this run (a K with no anneals costs L_K)."""
    Sk = sk_of(run['method'])
    m = run['method']
    out = []
    for K in range(1, Rmax + 1):
        v = run['cnt'].get(str(K))
        F = v['flips'] / v['anneals'] if v and v['anneals'] else 0.0
        if m.startswith('abl_fam_'):                                       # SA, A5.5 model E: S N + F, N = 2K copies of 2 Nr coordinates (16-QAM)
            out.append(int(m.split('_')[2]) * 4 * K * run['Nr'] + F)
        else:
            out.append(Sk * 2 * K + F)
    return np.array(out)


def stop(run, c, cyc, dN0_dB=0.0):
    """First-pass stop at threshold Nr + c sqrt(Nr) on t = d / N0, with N0 misestimated by dN0_dB. Per-use bit errors, cycles, stop index."""
    t = run['t'] * 10 ** (-dN0_dB / 10.0)
    thr = run['Nr'] + c * math.sqrt(run['Nr'])
    U, J = t.shape
    hit = t <= thr
    first = np.where(hit.any(1), hit.argmax(1), J - 1)
    a = np.arange(U)
    C = np.concatenate([np.zeros((U, 1)), np.cumsum((run['ann'] * cyc).sum(-1), 1)], 1)
    return run['be'][a, first].astype(np.int64), C[a, first], first


def nostop_cycles(run, cyc):
    return (run['ann'] * cyc).sum((1, 2))


def boot_ratio(a, b, B=4000, seed=12345):
    """Paired cluster bootstrap of sum(a) / sum(b) over uses (same index for both). Returns ratio, lo, hi. An exact bootstrap restricted to the
    uses where either has errors; the others do not change either sum."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    U = len(a)
    if U == 0:
        return None, None, None
    nz = np.nonzero((a > 0) | (b > 0))[0]
    sa, sb = a.sum(), b.sum()
    r0 = sa / sb if sb > 0 else (float('inf') if sa > 0 else 1.0)
    if len(nz) == 0:
        return 1.0, 1.0, 1.0
    rng = np.random.default_rng(seed)
    x, y = a[nz], b[nz]
    rs = np.empty(B)
    for i in range(B):
        n = rng.binomial(U, len(nz) / U)
        w = np.bincount(rng.integers(0, len(nz), n), minlength=len(nz))
        ya = float((w * x).sum()); yb = float((w * y).sum())
        rs[i] = ya / yb if yb > 0 else (float('inf') if ya > 0 else 1.0)
    rs.sort()                                                              # order statistics: a replicate with a zero denominator is +inf
    return float(r0), float(rs[int(0.025 * (B - 1))]), float(rs[int(math.ceil(0.975 * (B - 1)))])


def mcnemar(a, b):
    """Exact two-sided McNemar on vector errors."""
    x, y = int(((a > 0) & (b == 0)).sum()), int(((a == 0) & (b > 0)).sum())
    n = x + y
    if n == 0:
        return 1.0, x, y
    k = min(x, y)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p), x, y


def pick_c(run, cyc, limit=1.10):
    """Largest c whose paired BER ratio to no stop has upper 95% bound <= limit; None if no c passes. Tuning seed only."""
    base = run['biterr'].astype(np.int64)
    best = None
    for c in C_GRID:
        be, _, _ = stop(run, c, cyc)
        r, lo, hi = boot_ratio(be, base)
        if hi is not None and hi <= limit:
            best = c
    return best


def stop_row(run, c, cyc, dN0_dB=0.0):
    base = run['biterr'].astype(np.int64)
    C0 = nostop_cycles(run, cyc)
    be, C, first = stop(run, c, cyc, dN0_dB)
    r, lo, hi = boot_ratio(be, base)
    p, x, y = mcnemar(be, base)
    return dict(c=c, dN0_dB=dN0_dB, uses=len(base), ratio=r, lo=lo, hi=hi, mcnemar_p=p, more=x, fewer=y, err_uses=int((be > 0).sum()),
                base_err_uses=int((base > 0).sum()), stop0=float((first == 0).mean()), mean_stage=float(first.mean()),
                cyc=float(C.mean()), cyc0=float(C0.mean()), saving=float(C0.mean() / max(C.mean(), 1e-9)), p99_cyc=float(np.percentile(C, 99)),
                max_cyc=float(C.max()))


def paired_row(arm, ref, ba=64, name=None, cyc_arm=None, cyc_ref=None):
    """arm vs ref on their common prefix of uses (same draws, same batch size)."""
    n = min(len(arm['biterr']), len(ref['biterr']))
    a, b = arm['biterr'][:n].astype(np.int64), ref['biterr'][:n].astype(np.int64)
    r, lo, hi = boot_ratio(a, b)
    p, x, y = mcnemar(a, b)
    row = dict(name=name or arm['method'], uses=n, arm_err_uses=int((a > 0).sum()), ref_err_uses=int((b > 0).sum()), ratio=r, lo=lo, hi=hi,
               mcnemar_p=p, arm_only=x, ref_only=y, ber=float(a.sum()) / (n * ba), ref_ber=float(b.sum()) / (n * ba))
    if cyc_arm is not None and cyc_ref is not None and arm['cnt']:            # a saved method without flip counts has no modeled cost here
        row['x_cycles'] = float((arm['ann'][:n] * cyc_arm).sum() / max((ref['ann'][:n] * cyc_ref).sum(), 1e-9))
    return row
