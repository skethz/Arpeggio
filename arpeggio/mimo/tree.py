"""CPU tree-search baselines on the real-valued model y = H l + n (levels l in the PAM alphabet), numba-parallel:
- sphere_decoder: exact ML by depth-first Schnorr-Euchner enumeration with radius update (Schnorr & Euchner 1994;
  Agrell et al. 2002), sorted QR (columns by increasing norm, Wubben et al. 2001); a node cap marks instances that did
  not finish (their result is the best leaf found and they are counted separately);
- kbest: breadth-first K-best (Guo & Nilsson 2006) with K survivors per level, same sorted QR; returns the K survivors'
  leaves and distances (for soft output)."""
import numpy as np
from numba import njit, prange


@njit(cache=True)
def _sorted_qr(H):
    m, n = H.shape
    Q = H.copy()
    R = np.zeros((n, n))
    perm = np.arange(n)
    norms = np.array([np.dot(Q[:, j], Q[:, j]) for j in range(n)])
    for i in range(n):
        k = i + np.argmin(norms[i:])
        if k != i:                                       # swap columns i and k
            for r in range(m):
                Q[r, i], Q[r, k] = Q[r, k], Q[r, i]
            for r in range(n):
                R[r, i], R[r, k] = R[r, k], R[r, i]
            norms[i], norms[k] = norms[k], norms[i]
            perm[i], perm[k] = perm[k], perm[i]
        R[i, i] = np.sqrt(norms[i])
        Q[:, i] /= R[i, i]
        for j in range(i + 1, n):
            R[i, j] = np.dot(Q[:, i], Q[:, j])
            Q[:, j] -= R[i, j] * Q[:, i]
            norms[j] -= R[i, j] ** 2
    return Q, R, perm


@njit(cache=True)
def _sd_one(R, yt, levels, cap):
    n = R.shape[0]
    L = levels.shape[0]
    best = np.zeros(n)
    best_d = np.inf
    x = np.zeros(n)
    pd = np.zeros(n + 1)                                 # partial distance above level k
    order = np.zeros((n, L), np.int64)
    pos = np.zeros(n, np.int64)
    ctr = np.zeros(n)
    nodes = 0
    k = n - 1
    # enumerate level k: candidates sorted by distance to the centre
    def_c = 0.0
    while True:
        if pos[k] == 0:
            c = yt[k]
            for j in range(k + 1, n):
                c -= R[k, j] * x[j]
            c /= R[k, k]
            ctr[k] = c
            dd = np.abs(levels - c)
            order[k] = np.argsort(dd)
        if pos[k] >= L:
            pos[k] = 0
            k += 1
            if k >= n:
                break
            continue
        li = order[k, pos[k]]
        pos[k] += 1
        x[k] = levels[li]
        e = R[k, k] * (x[k] - ctr[k])
        d = pd[k + 1] + e * e
        nodes += 1
        if d >= best_d:                                  # sorted: the rest of this level is worse
            pos[k] = 0
            k += 1
            if k >= n:
                break
            continue
        if k == 0:
            best_d = d
            best[:] = x
            continue
        pd[k] = d
        k -= 1
        if nodes > cap:
            return best, best_d, nodes, False
    return best, best_d, nodes, True


@njit(parallel=True, cache=True)
def sphere_decoder(H, y, levels, cap):
    B, m, n = H.shape
    out = np.zeros((B, n))
    nodes = np.zeros(B, np.int64)
    done = np.zeros(B, np.bool_)
    for b in prange(B):
        Q, R, perm = _sorted_qr(H[b])
        yt = Q.T @ y[b]
        xb, d, nd, ok = _sd_one(R, yt, levels, cap)
        for j in range(n):
            out[b, perm[j]] = xb[j]
        nodes[b] = nd
        done[b] = ok
    return out, nodes, done


@njit(cache=True)
def _kbest_one(R, yt, levels, K):
    n = R.shape[0]
    L = levels.shape[0]
    surv = np.zeros((K, n))
    sd = np.zeros(K)
    ns = 1
    for k in range(n - 1, -1, -1):
        cand = np.zeros((ns * L, n))
        cd = np.zeros(ns * L)
        t = 0
        for i in range(ns):
            c = yt[k]
            for j in range(k + 1, n):
                c -= R[k, j] * surv[i, j]
            for li in range(L):
                e = c - R[k, k] * levels[li]
                cand[t] = surv[i]
                cand[t, k] = levels[li]
                cd[t] = sd[i] + e * e
                t += 1
        idx = np.argsort(cd[:t])
        ns = min(K, t)
        for i in range(ns):
            surv[i] = cand[idx[i]]
            sd[i] = cd[idx[i]]
    return surv[:ns], sd[:ns], ns


@njit(parallel=True, cache=True)
def kbest(H, y, levels, K):
    B, m, n = H.shape
    out = np.zeros((B, K, n))
    dists = np.full((B, K), np.inf)
    for b in prange(B):
        Q, R, perm = _sorted_qr(H[b])
        yt = Q.T @ y[b]
        surv, sd, ns = _kbest_one(R, yt, levels, K)
        rest = np.dot(yt, yt) * 0.0
        for i in range(ns):
            for j in range(n):
                out[b, i, perm[j]] = surv[i, j]
            dists[b, i] = sd[i]
    return out, dists


# ---------------------------------------------------------------- milestone B: K-best without path copies
@njit(cache=True)
def _kbest_one2(R, yt, levels, K):
    """Same survivors as _kbest_one (same candidate order and sort), but candidates are (parent, level) pairs and only
    the K selected paths are copied: O(K n) per level instead of O(K L n)."""
    n = R.shape[0]
    L = levels.shape[0]
    surv = np.zeros((K, n))
    new = np.zeros((K, n))
    sd = np.zeros(K)
    sd2 = np.zeros(K)
    cd = np.zeros(K * L)
    cpar = np.zeros(K * L, np.int64)
    clev = np.zeros(K * L)
    ns = 1
    for k in range(n - 1, -1, -1):
        t = 0
        for i in range(ns):
            c = yt[k]
            for j in range(k + 1, n):
                c -= R[k, j] * surv[i, j]
            for li in range(L):
                e = c - R[k, k] * levels[li]
                cd[t] = sd[i] + e * e
                cpar[t] = i
                clev[t] = levels[li]
                t += 1
        idx = np.argsort(cd[:t])
        ns2 = min(K, t)
        for qq in range(ns2):
            p = cpar[idx[qq]]
            for j in range(k + 1, n):
                new[qq, j] = surv[p, j]
            new[qq, k] = clev[idx[qq]]
            sd2[qq] = cd[idx[qq]]
        surv, new = new, surv
        sd, sd2 = sd2, sd
        ns = ns2
    return surv[:ns], sd[:ns], ns


@njit(parallel=True, cache=True)
def kbest2(H, y, levels, K):
    """K-best (Guo & Nilsson 2006) with sorted QR; returns the best leaf (B, n) and its distance. Identical decisions
    to kbest()[0][:, 0] (test_tree.py)."""
    B, m, n = H.shape
    out = np.zeros((B, n))
    dists = np.zeros(B)
    for b in prange(B):
        Q, R, perm = _sorted_qr(H[b])
        yt = Q.T @ y[b]
        surv, sd, ns = _kbest_one2(R, yt, levels, K)
        for j in range(n):
            out[b, perm[j]] = surv[0, j]
        dists[b] = sd[0]
    return out, dists
