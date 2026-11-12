"""Statistics of PROTOCOL.md section 5 (pure numpy; runs locally or on the hosts).

- snr_at(points, target): SNR at which BER crosses target, log-linear interpolation between grid points, using the
  LAST downward crossing (the pair (s0, s1) with BER(s0) >= target > BER(s1) after which no point is >= target).
  A zero-error point s1 is replaced by its one-sided 95 % upper bound 3/n (rule of three, n = bits); if any zero-error
  point is used the result is an upper bound and flagged 'le'. If the bound 3/n itself is >= target the crossing is
  reported as '<= s1'. If the curve never falls below target: '>' max SNR. If it starts below: '<=' min SNR.
- Cluster bootstrap: channel uses are the clusters (all bit errors of a use stay together); each SNR point is
  resampled independently (points are independent draws); BER* = sum(biterr*) / bits; percentile 95 % intervals.
- Paired bootstrap of a difference between two curves on the same draws: the common prefix of uses of a point is
  resampled with one index vector for both curves; the tails beyond the shorter run are resampled independently.
- McNemar: exact two-sided binomial test on vector errors over the common prefix of uses."""
import math

import numpy as np


def bound(err, bits):
    return (3.0 / bits, True) if err == 0 else (err / bits, False)


def snr_at(points, target):
    """points: list of (snr, err, bits). Returns dict(value, kind) kind in {'=', 'le', '>', 'le_grid', '<='}."""
    pts = sorted(points)
    if not pts:
        return dict(value=None, kind='none')
    b = [bound(e, n) for _, e, n in pts]
    s = [p[0] for p in pts]
    above = [bb[0] >= target and not bb[1] for bb in b]                  # a zero-error bound is never "above"
    if not any(above):
        return dict(value=s[0], kind='<=')
    last = max(i for i, a in enumerate(above) if a)
    if last == len(pts) - 1:
        return dict(value=s[-1], kind='>')
    s0, (b0, _) = s[last], b[last]
    s1, (b1, z1) = s[last + 1], b[last + 1]
    if b1 >= target:                                                       # only possible for a zero-error bound
        return dict(value=s1, kind='le_grid')
    v = s0 + (s1 - s0) * (math.log10(b0) - math.log10(target)) / (math.log10(b0) - math.log10(b1))
    return dict(value=v, kind='le' if z1 else '=')


def fmt_cross(c, nd=1):
    if c['value'] is None:
        return '--'
    v = ('%.' + str(nd) + 'f') % c['value']
    return {'=': v, 'le': '≤' + v, '>': '>' + v, 'le_grid': '≤' + v, '<=': '≤' + v}[c['kind']]


def cp_interval(err, bits, alpha=0.05):
    """Clopper-Pearson interval (binomial, ignores clustering; reported only beside the cluster bootstrap)."""
    from scipy.stats import beta
    lo = 0.0 if err == 0 else beta.ppf(alpha / 2, err, bits - err + 1)
    hi = 1.0 if err == bits else beta.ppf(1 - alpha / 2, err + 1, bits - err)
    return lo, hi


def boot_ber(biterr, bits_per_use, B=2000, rng=None):
    """Cluster bootstrap of BER for one point: biterr (n,) per-use bit errors. Returns (lo, hi, reps)."""
    rng = rng or np.random.default_rng(12345)
    n = len(biterr)
    reps = np.empty(B)
    for k in range(B):
        idx = rng.integers(0, n, n)
        reps[k] = biterr[idx].sum() / (n * bits_per_use)
    return np.percentile(reps, 2.5), np.percentile(reps, 97.5), reps


def boot_cross(curve, bits_per_use, target, B=2000, rng=None):
    """curve: dict snr -> biterr array. Bootstrap distribution of snr_at (zero-error replicates use 3/n)."""
    rng = rng or np.random.default_rng(54321)
    snrs = sorted(curve)
    vals, kinds = [], []
    for k in range(B):
        pts = []
        for s in snrs:
            be = curve[s]
            n = len(be)
            idx = rng.integers(0, n, n)
            pts.append((s, int(be[idx].sum()), n * bits_per_use))
        c = snr_at(pts, target)
        vals.append(c['value']); kinds.append(c['kind'])
    v = np.array([x if x is not None else np.nan for x in vals], float)
    return np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5), v, kinds


def boot_cross_diff(cA, cB, bits_per_use, target, B=2000, rng=None):
    """Paired bootstrap of snr_at(A) - snr_at(B) on shared draws (common prefix resampled jointly)."""
    rng = rng or np.random.default_rng(777)
    snrs = sorted(set(cA) | set(cB))
    out = np.empty(B)
    for k in range(B):
        pA, pB = [], []
        for s in snrs:
            a, bb = cA.get(s), cB.get(s)
            if a is not None and bb is not None:
                m = min(len(a), len(bb))
                idx = rng.integers(0, m, m)
                ea, eb = a[idx].sum(), bb[idx].sum()
                if len(a) > m:
                    ea += a[m + rng.integers(0, len(a) - m, len(a) - m)].sum()
                if len(bb) > m:
                    eb += bb[m + rng.integers(0, len(bb) - m, len(bb) - m)].sum()
                pA.append((s, int(ea), len(a) * bits_per_use)); pB.append((s, int(eb), len(bb) * bits_per_use))
            elif a is not None:
                idx = rng.integers(0, len(a), len(a)); pA.append((s, int(a[idx].sum()), len(a) * bits_per_use))
            else:
                idx = rng.integers(0, len(bb), len(bb)); pB.append((s, int(bb[idx].sum()), len(bb) * bits_per_use))
        xa, xb = snr_at(pA, target)['value'], snr_at(pB, target)['value']
        out[k] = np.nan if xa is None or xb is None else xa - xb
    return np.nanpercentile(out, 2.5), np.nanpercentile(out, 97.5), out


def mcnemar(vecA, vecB):
    """vecA, vecB: per-use vector-error booleans on the same draws (common prefix). Exact two-sided p-value."""
    m = min(len(vecA), len(vecB))
    a, b = vecA[:m].astype(bool), vecB[:m].astype(bool)
    n10 = int((a & ~b).sum())
    n01 = int((~a & b).sum())
    n = n10 + n01
    if n == 0:
        return dict(n10=0, n01=0, p=1.0, m=m)
    from scipy.stats import binomtest
    return dict(n10=n10, n01=n01, p=float(binomtest(n10, n, 0.5).pvalue), m=m)
