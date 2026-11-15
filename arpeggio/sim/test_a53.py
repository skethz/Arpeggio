#!/usr/bin/env python3
"""A5.3 dev checks (dev seed 9600; not held-out): (1) sa_seq returns bit-identical states with and without the flip
counter (the counter only reads acc); (2) abl_sao_<S>_<Ns> resolves to the sa pick (2.4 -> 0.05) and equals abl_sa_<Ns> at S = 128
for the same solver generator; (3) flip counts are plausible (0 < flips <= decisions)."""
import json, torch, arpx, mimo
ctx = arpx.Ctx(dict(sa=dict(T0=2.4, T1=0.05), sa2=dict(T0=2.4, T1=0.0125)))
b = arpx.draw(9600, 20.0, 0, 64, 16, 16)
z, _, _ = mimo.mmse(b)
lm = mimo.quantize_levels(z / mimo._mu(b, z), 16)
ok = True
for K in (1, 2):
    I = mimo.ising_delta_at(b, lm, K)
    for S in (1, 8):
        g1 = torch.Generator(device='cuda'); g1.manual_seed(3)
        a = arpx.sa_seq(I, 4, S, 2.4, 0.05, K, gen=g1)
        g2 = torch.Generator(device='cuda'); g2.manual_seed(3)
        cnt = {}
        c = arpx.sa_seq(I, 4, S, 2.4, 0.05, K, gen=g2, count=cnt)
        same = torch.equal(a, c)
        d = cnt[K]
        plaus = 0 < d['flips'] <= d['decisions'] and d['anneals'] == 64 * 4 and d['decisions'] == 64 * 4 * S * d['N']
        ok &= same and plaus
        print('K', K, 'S', S, 'identical', same, 'flips/anneal %.1f' % (d['flips'] / d['anneals']),
              'acc frac %.3f' % (d['flips'] / d['decisions']), 'plausible', plaus)
lhs = {}
bl = arpx.draw(9600, 14.0, 0, 64, 16, 16)                                # low SNR, so that errors occur
for m in ('abl_sao_128_32', 'abl_sa_32'):
    gs = torch.Generator(device='cuda'); gs.manual_seed(11)
    lh, dg, info = arpx.detect(m, bl, 'x16', gs, ctx)
    lhs[m] = lh
    print(m, 'bit errors at 14 dB', int(arpx.biterr_per_use(bl, lh).sum()))
same = torch.equal(lhs['abl_sao_128_32'], lhs['abl_sa_32'])
ok &= same
print('sao_128 decisions identical to sa (same generator):', same)
print('ALL OK' if ok else 'FAIL')
