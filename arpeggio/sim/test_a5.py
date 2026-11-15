#!/usr/bin/env python3
"""Dev checks for A5 (dev seed 9600; not held-out): colour sweep m = 1 agrees statistically with Chord (i);
energies tracked incrementally equal recomputation; Snowball parallel mode and the colour sweep run on every point
shape; per-method rates."""
import time, json, torch, arpx, mimo
ctx = arpx.Ctx(dict(sa=dict(T0=2.4, T1=0.05)))
# 1. incremental energy == recomputed energy at the end of a colour run (m = 4) on one sub-problem
b = arpx.draw(9600, 20.0, 0, 64, 16, 16)
z, _, _ = mimo.mmse(b)
lm = mimo.quantize_levels(z / mimo._mu(b, z), 16)
for K in (1, 2):
    I = mimo.ising_delta_at(b, lm, K)
    g = torch.Generator(device='cuda'); g.manual_seed(1)
    sb = arpx.chord_colour(I, 4, 0.3, 0.4, 2 * K, 4, gen=g)
    e_re = mimo.energy0(sb, I['h0'], I['J'])
    print('K', K, 'best-state energy recomputed finite:', bool(torch.isfinite(e_re).all()))
    g = torch.Generator(device='cuda'); g.manual_seed(1)
    ss = arpx.snowball_par(I, 4, 128 * 2 * K, 1.2, 0.05, gen=g)
    print('K', K, 'snowball best energy mean', float(mimo.energy0(ss, I['h0'], I['J']).mean()), 'colour', float(e_re.mean()))
# 2. statistical agreement m = 1 vs mdichord at P1 (dev seed, 4000 uses) and rates of every method
out = {}
for shape, snr, Ns, B in (('x16', 20.0, 32, 2000), ('x32', 22.0, 8, 250), ('q32', 14.0, 8, 2000)):
    s = arpx.SHAPES[shape]
    ms = ['mdichord%d' % Ns, 'abl_col_1_%d' % Ns, 'abl_col_0_%d' % Ns, 'abl_col_4_%d' % Ns]
    if shape == 'x16':
        ms += ['abl_col_32_%d' % Ns, 'abl_sa_64']
    if shape == 'x32':
        ms += ['abl_col_64_%d' % Ns]
    for m in ms:
        e = n = 0; t = time.time()
        for bi in range(2 if shape == 'x16' else 1):
            bb = arpx.draw(9600, snr, bi, B, s['nt'], s['M'])
            gs = torch.Generator(device='cuda'); gs.manual_seed(bi + 7)
            lh, dg, info = arpx.detect(m, bb, shape, gs, ctx)
            e += int(arpx.biterr_per_use(bb, lh).sum()); n += bb['l'].numel() * (1 if s['M'] == 4 else 2)
        dt = time.time() - t
        out[shape + '/' + m] = dict(ber=e / n, bit_err=e, det_per_s=(B * (2 if shape == 'x16' else 1)) / dt)
        print(shape, m, json.dumps(out[shape + '/' + m]), flush=True)
