#!/usr/bin/env python3
"""Checks of the new code before any held-out run (dev seed 9200; PROTOCOL.md 2):
1. apx.mdi_diag returns exactly mimo.mdi's decisions with the same solver random numbers (AHC and Antiphase, 16-QAM
   and QPSK); its inbox diagnostics are consistent (inbox_s1 implies inbox_any).
2. apx.anechoic_ext with a constant per-spin q, the copy phases and no dilution equals mimo.anechoic bit for bit.
3. Every detector and ablation variant runs on each point shape and returns constellation levels.
4. CPU draws are deterministic (two calls give identical tensors)."""
import sys
import time

import torch

import apx
import mimo

ok = True


def check(name, cond, msg=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + (': ' + msg if msg else ''), flush=True)
    ok = ok and bool(cond)


b1 = apx.draw(9200, 20.0, 0, 64, 16, 16); b2 = apx.draw(9200, 20.0, 0, 64, 16, 16)
check('draw deterministic', all(torch.equal(b1[k], b2[k]) for k in ('H', 'y', 'l')))

for shape, snr, B in (('x16', 20.0, 300), ('q32', 12.0, 500)):
    s = apx.SHAPES[shape]
    b = apx.draw(9200, snr, 1, B, s['nt'], s['M'])
    z, _, _ = mimo.mmse(b)
    c = s['mdi']
    for name, mk in (('ane', lambda g: (lambda I, na, K: mimo.anechoic(I, na, 128 * 2 * K, 0.3, 0.3, 0.4, gen=g, phases=2 * K))),
                     ('ahc', lambda g: (lambda I, na, K: mimo.ahc(I, na, gen=g)))):
        g1 = torch.Generator(device='cuda'); g1.manual_seed(5)
        g2 = torch.Generator(device='cuda'); g2.manual_seed(5)
        l_ref = mimo.mdi(b, mk(g1), 16, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z)
        l_new, dg = apx.mdi_diag(b, mk(g2), 16, c['Rmax'], c['S'], guesses=c['guesses'], z_mmse=z)
        check('mdi_diag == mimo.mdi %s %s' % (shape, name), torch.equal(l_ref, l_new))
        check('inbox_s1 => inbox_any %s %s' % (shape, name), bool((~dg['inbox_s1'] | dg['inbox_any']).all()),
              'inbox_any %.3f inbox_s1 %.3f' % (dg['inbox_any'].float().mean(), dg['inbox_s1'].float().mean()))

b = apx.draw(9200, 20.0, 2, 50, 16, 16)
z, _, _ = mimo.mmse(b)
lm = mimo.quantize_levels(z / mimo._mu(b, z), 16)
for K in (1, 2):
    I = mimo.ising_delta_at(b, lm, K)
    g1 = torch.Generator(device='cuda'); g1.manual_seed(9)
    g2 = torch.Generator(device='cuda'); g2.manual_seed(9)
    s_ref = mimo.anechoic(I, 5, 128 * 2 * K, 0.3, 0.3, 0.4, gen=g1, phases=2 * K)
    qv = torch.full_like(I['h0'], 0.4)
    s_new = apx.anechoic_ext(I, 5, 128 * 2 * K, 0.3, qv, phases=2 * K, gen=g2)
    check('anechoic_ext == mimo.anechoic K=%d' % K, torch.equal(s_ref, s_new))
    gd = apx.gdiag(I, K)
    Gm = torch.diagonal(b['H'].transpose(1, 2) @ b['H'], dim1=-2, dim2=-1) / I['scale'][:, None]
    check('gdiag = diag(H^T H)/scale K=%d' % K, torch.allclose(gd[:, :32], Gm, rtol=1e-5, atol=1e-6))

ctx = apx.Ctx(dict(qdim=dict(c=0.5, q0=0.0, T=0.3), sa=dict(T0=0.6, T1=0.05), sym=dict(T=0.2)))
lv = {16: torch.tensor([-3., -1., 1., 3.]), 4: torch.tensor([-1., 1.])}
for shape, snr, B, Ns in (('x16', 20.0, 40, 32), ('x32', 22.0, 16, 8), ('q32', 14.0, 64, 8), ('q16', 12.0, 64, 64)):
    s = apx.SHAPES[shape]
    b = apx.draw(9200, snr, 3, B, s['nt'], s['M'])
    ms = ['mmse', 'sic', 'mdiane%d' % Ns, 'mdiahc%d' % Ns] + ['abl_%s_%d' % (v, Ns) for v in
                                                               ('noalt', 'noaltq0', 'q0', 'qdim', 'dil', 'final', 'ons', 'pimi', 'sa', 'sym')]
    ms += ['abl_qt_a_0.2_0.5_%d' % Ns, 'abl_qdimc_1_0_0.3_%d' % Ns, 'abl_sat_1.2_0.05_%d' % Ns, 'abl_symt_0.4_%d' % Ns]
    if shape in ('x16', 'x32'):
        ms += ['aned64', 'kbest32']
    if shape in ('q16', 'q32'):
        ms += ['ane64ri', 'mdiahck%d' % Ns]
    if shape in ('x16', 'q16'):
        ms += ['sd']
    for m in ms:
        gs = torch.Generator(device='cuda'); gs.manual_seed(11)
        t0 = time.time()
        try:
            lh, dg, info = apx.detect(m, b, shape, gs, ctx)
            okl = bool(torch.isin(lh, lv[s['M']].to(lh.device)).all()) and lh.shape == b['l'].shape
            e = int(apx.biterr_per_use(b, lh).sum())
            check('%s %s' % (shape, m), okl, 'bit errors %d in %d uses, %.1f s' % (e, B, time.time() - t0))
        except Exception as ex:
            check('%s %s' % (shape, m), False, repr(ex))
print('ALL PASS' if ok else 'SOME FAIL')
sys.exit(0 if ok else 1)
