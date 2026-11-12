#!/usr/bin/env python3
"""A5.14 gates G1 and G3 (PROTOCOL_A514.md section 4) on real sub-problems of dev seed 9600 (never a held-out or tuning seed).
G1: fa_seq_w(force=True) at W = 1 equals apx55.fa_seq rule 'r' bit for bit (best spins and every counter), and fa_seq_w at W = 1
    without force is apx55.fa_seq itself.
G3: at W = 2 and 4, fa_seq_w equals ref_w, a per-anneal loop written from the definition with the same random-number calls, bit
    for bit; the tracked energy matches a recomputation (|dE| < 1e-3); tests = S P anneals + commits - last.
Usage: gate_a514.py OUT.json"""
import json
import sys

import torch

import apx
import apx55
import apx514
import mdi_solvers

mimo = apx.mimo
c = mdi_solvers.MDI[('64x64', 16)]
apx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(c['Rmax']), S=int(c['S']), guesses=tuple(c['guesses'])), Ns_pub=None))


@torch.no_grad()
def ref_w(I, R, S, T0, T1, K, W, q, start, gen):
    """Definition: per anneal and pass, test the remaining lanes on the current fields; commit the first min(W, accepted) in scan
    order one by one (fields updated after each); continue from the lane after the last commit. Same random-number calls."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    dev = h.device
    P = 2 * K
    D = N // P
    A = B * R
    s = apx55.start_spins(B, R, N, P, start, gen, dev)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = mimo.energy0(s, h0, J)
    s, u, E = s.reshape(A, N).clone(), u.reshape(A, N).clone(), E.reshape(A).clone()
    best_s, best_e = s.clone(), E.clone()
    Ts = mimo.geom(T0, T1, S, dev).tolist()
    Jt = J.transpose(1, 2).contiguous()
    rnds = [torch.rand(B, R, N, generator=gen, device=dev).reshape(A, N) for _ in range(S)]
    for a in range(A):
        b = a // R
        for sw in range(S):
            T = Ts[sw]
            rnd = rnds[sw]
            for p in range(P):
                lo = p * D
                ptr = 0
                while ptr < D:
                    ss, uu, rr = s[a:a + 1, lo:lo + D], u[a:a + 1, lo:lo + D], rnd[a:a + 1, lo:lo + D]
                    acc = ((ss * uu + q) < ((rr - 0.5) * 4 * T))[0]
                    idx = [j for j in range(ptr, D) if bool(acc[j])][:W]
                    if not idx:
                        break
                    for j in idx:
                        g = lo + j
                        si = s[a:a + 1, g]
                        de = 2 * si * u[a:a + 1, g]
                        delta = -2 * si
                        u[a:a + 1] += 2 * delta[:, None] * Jt[b:b + 1, g]
                        s[a:a + 1, g] = si + delta
                        E[a:a + 1] += de
                    ptr = idx[-1] + 1
                if bool(E[a] < best_e[a]):
                    best_e[a] = E[a]
                    best_s[a] = s[a]
    return best_s.reshape(B, R, N)


def cases():
    """Real sub-problems: MMSE-guess Ising deltas at K = 1, 2, 3 for P1, P2, P4 shapes, dev seed 9600."""
    for pt, (shape, snr) in dict(P1=('x16', 20.0), P2=('x32', 22.0), P4=('x64', 22.0)).items():
        sp = apx.SHAPES[shape]
        bt = apx.draw(9600, snr, 0, 4, sp['nt'], sp['M'])
        z, _, _ = mimo.mmse(bt)
        guess = mimo.quantize_levels(z / mimo._mu(bt, z), sp['M'])
        for K in (1, 2, 3):
            yield pt, K, mimo.ising_delta_at(bt, guess, K)


out = dict(G1=[], G3=[])
ok = True
for pt, K, I in cases():
    for st in ('rand', 'bal'):
        for (S, T, q) in ((8, 0.1, 0.0), (4, 0.3, 0.2)):
            g1, g2 = torch.Generator(device='cuda'), torch.Generator(device='cuda')
            g1.manual_seed(77); g2.manual_seed(77)
            c1, c2 = {}, {}
            a = apx55.fa_seq(I, 3, S, T, T, K, rule='r', q=q, start=st, gen=g1, count=c1)
            b = apx514.fa_seq_w(I, 3, S, T, T, K, 1, q=q, start=st, gen=g2, count=c2, force=True)
            same = bool(torch.equal(a, b)) and all(c1[K][k] == c2[K][k] for k in c1[K])
            out['G1'].append(dict(pt=pt, K=K, start=st, S=S, T=T, q=q, identical=same))
            ok &= same
            for W in (2, 4):
                g1.manual_seed(91); g2.manual_seed(91)
                au, cw = {}, {}
                a = apx514.fa_seq_w(I, 2, S, T, T, K, W, q=q, start=st, gen=g1, count=cw, audit=au)
                b = ref_w(I, 2, S, T, T, K, W, q, st, g2)
                same = bool(torch.equal(a, b))
                good = same and au['max_dE'] < 1e-3 and au['tests_identity']
                out['G3'].append(dict(pt=pt, K=K, start=st, S=S, T=T, q=q, W=W, identical=same, max_dE=au['max_dE'],
                                      tests_identity=au['tests_identity'], flips=cw[K]['flips'], commits=cw[K]['commits']))
                ok &= good
            print(pt, K, st, S, T, q, 'G1', out['G1'][-1]['identical'], 'G3', [(r['W'], r['identical'], '%.1e' % r['max_dE'])
                                                                               for r in out['G3'][-2:]], flush=True)
out['PASS'] = bool(ok)
json.dump(out, open(sys.argv[1], 'w'), indent=1)
print('G1/G3', 'PASS' if ok else 'FAIL', flush=True)
