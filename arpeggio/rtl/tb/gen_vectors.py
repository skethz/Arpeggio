"""Stimulus and expected results for the RTL testbench from captured held-out MDI sub-problems.

Program: the schedule table (768 entries of the frozen MDI schedule: T 0.3, q 0.4, c 0), then per instance the
G rows, h, and RUNs for K in Ks (queued back to back, sharing G and h). Writes <out>/stim.txt and <out>/expected.json:
model beats (cycle, tag, r, p, bits, Δbest) and acceptance cycles (ape_model.cpp, same build: philox or xs), plus for
the Philox build the original reference's results (anefx.anechoic_fx: best spins and best_e - e0) per (tag, anneal).
Usage: gen_vectors.py <study_src> <capture.pt> <out dir> <rng: philox|xs> <n instances> <Ks e.g. 1,2,3> <R> <A> <SEEDL>
"""
import sys, os, json
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'model'))
import numpy as np
import torch
import anefx
import antiphase_ref as ar
import ape_py
torch.set_num_threads(8)

cap_path, out, rng, ninst, Ks, R, A, SEEDL = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), \
    [int(x) for x in sys.argv[6].split(',')], int(sys.argv[7]), int(sys.argv[8]), int(sys.argv[9])
os.makedirs(out, exist_ok=True)
cap = torch.load(cap_path)
CW = 14
# instances: walk the captured calls, take instances in order (real MDI sub-problems of several stages)
Gs, hs, ids = [], [], []
for rec in cap['recs']:
    for b in range(rec['G'].shape[0]):
        if len(Gs) < ninst:
            Gs.append(rec['G'][b].long()); hs.append(rec['h'][b].long()); ids.append((rec['call'], b))
D = Gs[0].shape[0]
dummy = dict(J=torch.zeros(1, 2, 2), h=torch.zeros(1, 2), h0=torch.zeros(1, 2))
F768 = anefx.to_fixed(dummy, 768, 0.3, 0.3, 0.4, 0.0)
T, c, q = F768['T'].tolist(), F768['c'].tolist(), F768['q']
seed0 = 0x5EED0000 + 7919 * ninst
pr = ape_py.Program(D)
pr.load_tab(T, c, 0)
tags = {}
for n_, (G, h) in enumerate(zip(Gs, hs)):
    pr.load_G(G.numpy()); pr.load_h(h.numpy())
    for K in Ks:
        tag = n_ * 4 + K
        tags[tag] = (n_, K)
        pr.run(2 * K, R, 128 * 2 * K, q, inst=1000 + n_, seed=seed0 + tag, tag=tag)
res = pr.execute(A=A, SEEDL=SEEDL, philox=1 if rng == 'philox' else 0)


def hexdata(vals):
    v = 0
    for j, x in enumerate(vals):
        v |= (int(x) & ((1 << CW) - 1)) << (j * CW)
    return '%x' % v


dall = np.concatenate(pr.data)
with open(os.path.join(out, 'stim.txt'), 'w') as f:
    for cmd in pr.cmds:
        if cmd.op in (ape_py.OP_LOAD_ROW, ape_py.OP_LOAD_H):
            off = cmd.data_off
            d = dall[off:off + D]
            f.write('%d %d %s\n' % (cmd.op, cmd.addr, hexdata(d)))
        elif cmd.op == ape_py.OP_LOAD_TAB:
            f.write('%d %d %x\n' % (cmd.op, cmd.addr, ((cmd.c & 0xFFFF) << 16) | (cmd.T & 0xFFFF)))
        elif cmd.op == ape_py.OP_RUN:
            v = (cmd.P | (cmd.R << 3) | (cmd.S << 15) | (cmd.tb << 25) | ((cmd.q & 0xFFFF) << 35) | (cmd.inst << 51)
                 | (cmd.seed << 83) | (cmd.tag << 147))
            f.write('%d %d %x\n' % (cmd.op, 0, v))
exp = dict(D=D, A=A, SEEDL=SEEDL, rng=rng, ncmd=len(pr.cmds), cycles=int(res['cycles']), acc=[int(x) for x in res['acc']],
           beats=[[int(res['beat_cycle'][i]), int(res['tag'][i]), int(res['r'][i]), int(res['p'][i]),
                   ''.join('1' if b else '0' for b in res['bits'][i][::-1]), int(res['de'][i])] for i in range(len(res['tag']))],
           tags={str(k): v for k, v in tags.items()}, stats=res['stats'], ids=ids)
# independent references per (tag, anneal)
refs = {}
for tag, (n_, K) in tags.items():
    G, h = Gs[n_][None], hs[n_][None]
    P = 2 * K; S = 128 * P
    if rng == 'philox':
        Jx, hx = ar.expand(G, h, K)
        F = dict(J=Jx, h=hx, h0=hx.clone(), T=torch.tensor(T[:S]), c=torch.tensor(c[:S]), q=q, S=S, Q=4096)
        bs, be = anefx.anechoic_fx(F, R, seed0 + tag, P=P, inst0=1000 + n_, mode='chains')
        e0 = ar.start_energy_anefx(F, R, seed0 + tag, P, 1000 + n_)
        de = be - e0
    else:
        bs, de, _ = ar.antiphase_ref(G, h, P, T[:S], c[:S], q, R, seed0 + tag, 1000 + n_, rng='xs')
    for r in range(R):
        refs['%d,%d' % (tag, r)] = [''.join('1' if x > 0 else '0' for x in bs[0, r].tolist()), int(de[0, r])]
exp['refs'] = refs
exp['ref_kind'] = 'anefx.anechoic_fx' if rng == 'philox' else 'antiphase_ref(xs)'
json.dump(exp, open(os.path.join(out, 'expected.json'), 'w'))
print('vectors', out, 'D', D, 'instances', len(Gs), 'Ks', Ks, 'R', R, 'commands', len(pr.cmds), 'beats', len(res['tag']),
      'model cycles', res['cycles'], 'stats', res['stats'])
