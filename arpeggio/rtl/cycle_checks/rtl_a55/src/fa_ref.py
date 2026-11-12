#!/usr/bin/env python3
"""A5.5 fixed-point reference (PROTOCOL_A55.md section 8) in plain Python integers, written from DESIGN's equations and not from the first-accept
RTL: an index-order sequential scan per pass with Philox4x32-10 numbers, one per (sweep, copy, lane). Also mode 'par' (v1.4's parallel half-step),
the baseline that the harness itself is right.
  gen OUT_DIR CAPTURE.pt S T0 T1 q start mode    write stim.txt and ref.json
  check OUT_DIR A                                compare rtl_events.txt with ref.json; prints PASS/FAIL lines; exit 1 on FAIL"""
import json, os, sys
M = 0xFFFFFFFF
CW, R, SEED, TAG0 = 14, 2, 0x1234567890ABCDEF, 1


def philox(c0, c1, c2, c3, k0, k1):
    for i in range(10):
        if i:
            k0 = (k0 + 0x9E3779B9) & M; k1 = (k1 + 0xBB67AE85) & M
        p0 = 0xD2511F53 * c0; p1 = 0xCD9E8D57 * c2
        n0 = (p1 >> 32) ^ c1 ^ k0; n2 = (p0 >> 32) ^ c3 ^ k1
        c1 = p1 & M; c3 = p0 & M; c0 = n0; c2 = n2
    return c0, c1, c2, c3


def hexd(v):
    x = 0
    for j, a in enumerate(v):
        x |= (int(a) & ((1 << CW) - 1)) << (j * CW)
    return '%x' % x


def bal_pat(P, i):
    n = 0
    for v in range(1 << P):
        if bin(v).count('1') == P // 2:
            if n == i:
                return v
            n += 1
    raise ValueError


def anneal(G, h, P, T, q, r, inst, start, mode):
    D, S = len(h), len(T)
    k0, k1 = SEED & M, (SEED >> 32) & M
    if start == 'rand':
        s = [[1 if philox(M, p * D + j, r, inst, k0, k1)[0] >= 2 ** 31 else -1 for j in range(D)] for p in range(P)]
    else:
        C = {2: 2, 4: 6, 6: 20}[P]
        pats = [bal_pat(P, (philox(M, j, r, inst, k0, k1)[0] * C) >> 32) for j in range(D)]
        s = [[1 if (pats[j] >> p) & 1 else -1 for j in range(D)] for p in range(P)]
    m = [sum(s[p][j] for p in range(P)) for j in range(D)]
    w = [h[i] - 2 * sum(G[i][j] * m[j] for j in range(D)) for i in range(D)]
    diag = [G[i][i] for i in range(D)]
    de, best, bs = 0, 1 << 62, None
    acc, tests, flips_k = [], [], []
    for k in range(S):
        p, n = k % P, k // P
        A, Bk = 4 * T[k], q + 2 * T[k]
        u = [philox(n >> 2, p * D + j, r, inst, k0, k1)[n & 3] for j in range(D)]
        if mode == 'fa':
            t = 1
            for j in range(D):
                if u[j] * A > (s[p][j] * w[j] + 2 * diag[j] + Bk) << 32:       # lanes after a flip see the updated field
                    so = s[p][j]
                    de += 4 * so * w[j] + 8 * diag[j]
                    for i in range(D):
                        w[i] += 4 * so * G[i][j]
                    s[p][j] = -so
                    acc.append((k, j))
                    if j < D - 1:
                        t += 1
            tests.append(t)
        else:
            F = [j for j in range(D) if u[j] * A > (s[p][j] * w[j] + 2 * diag[j] + Bk) << 32]
            for j in F:
                so = s[p][j]
                de += 4 * so * w[j] + 8 * diag[j]
                for i in range(D):
                    w[i] += 4 * so * G[i][j]
                s[p][j] = -so
                acc.append((k, j))
            tests.append(1)
        if de < best:
            best, bs = de, [''.join('1' if s[pp][j] > 0 else '0' for j in reversed(range(D))) for pp in range(P)]
    return dict(acc=acc, tests=tests, best=best, bs=bs, init=sum(1 for x in m if x))


def gen(out, cap, S, T0, T1, q, start, mode):
    import torch
    sys.path.insert(0, os.environ.get('MIMO_SRC', '<SCRATCH>/ap_ber_20261024/code_mimo/src'))
    import anefx, mimo
    os.makedirs(out, exist_ok=True)
    D_ = torch.load(cap)
    Q = anefx.QSCALE
    Tsw = [int(round(v * Q)) for v in mimo.geom(T0, T1, S, 'cpu').double().tolist()]
    qi = int(round(q * Q))
    ref, cmds, tag = {}, [], TAG0
    for K in (1, 2, 3):
        P = 2 * K
        T = [t for t in Tsw for _ in range(P)] if mode == 'fa' else Tsw
        for k, t in enumerate(T):
            cmds.append('3 %d %x' % (k, t & 0xFFFF))                            # c = 0
        G_, h_ = D_[K]['G'], D_[K]['h']
        for b in range(G_.shape[0]):
            G, h = G_[b].tolist(), h_[b].tolist()
            D = len(h)
            for i in range(D):
                cmds.append('1 %d %s' % (i, hexd(G[i])))
            cmds.append('2 0 %s' % hexd(h))
            inst = 1000 * K + b
            v = P | (R << 3) | (len(T) << 15) | ((qi & 0xFFFF) << 35) | (inst << 51) | (SEED << 83) | (tag << 147)
            cmds.append('4 0 %x' % v)
            for r in range(R):
                ref['%d/%d' % (tag, r)] = dict(anneal(G, h, P, T, qi, r, inst, start, mode), K=K, P=P, S=len(T), sweeps=S)
            tag += 1
    with open(os.path.join(out, 'stim.txt'), 'w') as f:
        f.write('\n'.join(cmds) + '\n')
    json.dump(dict(ref=ref, mode=mode, start=start, S=S, T0=T0, T1=T1, q=q), open(os.path.join(out, 'ref.json'), 'w'))
    print('generated', out, len(ref), 'anneals', sum(len(v['acc']) for v in ref.values()), 'flips', sum(sum(v['tests']) for v in ref.values()), 'tests')


def check(out, A):
    J = json.load(open(os.path.join(out, 'ref.json')))
    ref, mode = J['ref'], J['mode']
    ev = {k: dict(T=[], T0=None, F=[], I=0, S=None, E=None, B={}, de=None) for k in ref}
    for line in open(os.path.join(out, 'rtl_events.txt')):
        a = line.split()
        key = '%s/%s' % (a[1], a[2])
        e = ev[key]
        if a[0] == 'T':
            e['T'].append(int(a[3]))
            if e['T0'] is None:
                e['T0'] = int(a[4])
        elif a[0] == 'F':
            e['F'].append((int(a[3]), int(a[4])))
        elif a[0] == 'I':
            e['I'] += 1
        elif a[0] == 'S':
            e['S'] = int(a[3])
        elif a[0] == 'E':
            e['E'] = int(a[3])
        elif a[0] == 'B':
            e['B'][int(a[3])] = a[4]; e['de'] = int(a[5])
    fails = {'accepted-lane sequence': 0, 'decision-port tests per pass': 0, 'R-port flips': 0, 'tests = S P + flips not on a last lane': 0,
             'best spins and energy': 0, 'init ops': 0, 'cycles = 3 tests + 2 F (A = 1)': 0}
    totT = totF = totC = 0
    D = 32
    for k, r in ref.items():
        e = ev[k]
        acc = [tuple(x) for x in r['acc']]
        if mode == 'fa':
            fails['accepted-lane sequence'] += e['F'] != acc
        else:
            fails['accepted-lane sequence'] += sorted(e['F']) != sorted(acc)
        tk = [0] * r['S']
        for x in e['T']:
            if x < r['S']:
                tk[x] += 1
        fails['decision-port tests per pass'] += tk != r['tests']
        fails['R-port flips'] += len(e['F']) != len(acc)
        nl = sum(1 for _, j in acc if j < D - 1)
        if mode == 'fa':
            fails['tests = S P + flips not on a last lane'] += sum(tk) != r['S'] + nl
        bs = [e['B'].get(p) for p in range(r['P'])]
        want = [('%x' % int(b, 2)).zfill(8) for b in r['bs']]
        fails['best spins and energy'] += bs != want or e['de'] != r['best']
        fails['init ops'] += e['I'] != r['init']
        if A == 1:
            c = e['E'] - e['T0'] if e['E'] is not None and e['T0'] is not None else -10 ** 9   # first D0 of the anneal to the first cycle in OUTQ
            want_c = 3 * sum(tk) + 2 * len(acc) if mode == 'fa' else None
            totC += c
            if want_c is not None:
                r['_c'] = c
                r['_w'] = want_c
        totT += sum(tk); totF += len(acc)
    if A == 1 and mode == 'fa':
        off = {r['_c'] - r['_w'] for r in ref.values()}
        print('cycles from first D0 to OUTQ, minus (3 tests + 2 F):', sorted(off))
        fails['cycles = 3 tests + 2 F (A = 1)'] += 0 if off == {0} else len(ref)
    bad = 0
    for name, n in fails.items():
        if A != 1 and name.startswith('cycles'):
            continue
        if mode != 'fa' and (name.startswith('tests =') or name.startswith('cycles')):
            continue
        print('%s %s (%d anneals, %d failed)' % ('PASS' if n == 0 else 'FAIL', name, len(ref), n))
        bad += n
    print('%s %s A=%d start=%s S=%d: %d anneals, %d tests, %d flips' % ('ALL PASS' if not bad else 'FAILED', mode, A, J['start'], J['S'], len(ref), totT, totF))
    return bad


if sys.argv[1] == 'gen':
    gen(sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7]), sys.argv[8], sys.argv[9])
else:
    sys.exit(1 if check(sys.argv[2], int(sys.argv[3])) else 0)
