#!/usr/bin/env python3
"""A5.18 part 2 W1 stimulus: 20 real MDI sub-problems per K on dev seed 9600 with x64 (MDI config as s2_counts.py), 22 dB, Ns 8, as 14-bit integer (G, h) from
chordfx.to_fixed and chord_ref.compress. No held-out draw is read. Usage: capture_a55.py OUT.pt"""
import sys, torch, arpx, runner_a55, arpx55, chordfx  # noqa: F401
sys.path.insert(0, '<SCRATCH>/arpeggio_ber_20261024/a518_rtl/src')
import chord_ref as ar
OUT = sys.argv[1]
import mdi_solvers
_c = mdi_solvers.MDI[('64x64', 16)]
arpx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(_c['Rmax']), S=int(_c['S']), guesses=tuple(_c['guesses'])), Ns_pub=None))
s = arpx.SHAPES['x64']; c = s['mdi']
rec = {1: [], 2: [], 3: []}
gs = torch.Generator(device='cuda'); gs.manual_seed(9600)


def solver(I, na, K):
    F = chordfx.to_fixed({k: v.cpu() for k, v in I.items() if k in ('J', 'h', 'h0')}, 8, 1.2, 0.1, 0.2, 0.0)
    G, h = ar.compress(F, K)
    for b in range(G.shape[0]):
        if len(rec[K]) < 20:
            rec[K].append((G[b].clone(), h[b].clone()))
    return arpx55.arpeggio_seq(I, na, 8, 1.2, 0.1, K, rule='r', q=0.2, start='rand', gen=gs)


for bi in range(40):
    b = arpx.draw(9600, 22.0, bi, 200, s['nt'], s['M'])
    arpx.mdi_diag(b, solver, 8, c['Rmax'], c['S'], guesses=c['guesses'])
    print('batch', bi, {K: len(v) for K, v in rec.items()}, flush=True)
    if all(len(v) >= 20 for v in rec.values()):
        break
assert all(len(v) == 20 for v in rec.values())
mx = max(max(int(g.abs().max()), int(h.abs().max())) for v in rec.values() for g, h in v)
assert mx < 2 ** 13, mx
torch.save({K: dict(G=torch.stack([g for g, _ in v]), h=torch.stack([h for _, h in v])) for K, v in rec.items()}, OUT)
print('saved', OUT, 'max |coef|', mx, 'Q', chordfx.QSCALE)
