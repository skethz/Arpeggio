#!/usr/bin/env python3
"""Dev checks of the A5/A5.1 code (dev seed 9700, tiny batches; not held-out, no timing claim):
1. colour classes partition the spins; at m = Nt each class has 2 spins (I and Q of one user, same copy) with J = 0
   between them (exact chromatic N/2 colouring); 'dim' mode gives P classes holding all copies of D/P dims;
2. every new method runs on its shapes and returns constellation levels."""
import torch, apx, mimo
ok = True
for shape, K in (('x16', 1), ('x16', 3), ('x32', 2), ('q32', 1)):
    s = apx.SHAPES[shape]
    b = apx.draw(9700, 20.0, 0, 8, s['nt'], s['M'])
    z, _, _ = mimo.mmse(b)
    lm = mimo.quantize_levels(z / mimo._mu(b, z), s['M'])
    I = mimo.ising_delta_at(b, lm, K)
    N = I['h'].shape[1]; P = 2 * K; Nt = s['nt']
    for mode, m in (('copy', 0), ('copy', 1), ('copy', 2), ('copy', Nt), ('dim', 0)):
        cl = apx.colour_classes(N, P, mode, m, I['h'].device)
        allix = torch.cat(cl).sort().values
        part = torch.equal(allix, torch.arange(N, device=allix.device))
        intra = max(float(I['J'][:, ix][:, :, ix].abs().amax()) for ix in cl) if mode == 'copy' and m == Nt else None
        print(shape, 'K', K, mode, m, 'classes', len(cl), 'partition', part, 'max |J| within class' if intra is not None else '', intra if intra is not None else '')
        ok &= part and (intra is None or intra < 1e-6)
ctx = apx.Ctx(dict(sa=dict(T0=2.4, T1=0.05), sa2=dict(T0=2.4, T1=0.05), flip_phi={'x16': {'1': .36, '2': .36, '3': .36}, 'x32': {'1': .36, '2': .36, '3': .36}, 'q32': {'1': .36}},
                   pt_cyc=dict(T0=1.2, T1=0.05), pt_fl=dict(T0=1.2, T1=0.05), pt_cyc_x32=dict(T0=1.2, T1=0.05), pt_fl_q32=dict(T0=1.2, T1=0.05),
                   col={'x16': {'0': dict(q=0.4, T=0.3), '16': dict(q=0.4, T=0.3)}, 'x32': {'32': dict(q=0.4, T=0.3)}},
                   dim=dict(q=0.4, T=0.3), symd=dict(T=0.4, q=0.2), qdim_pp={'x32': dict(c=1, q0=0.4, T=0.6)}))
lv = {16: torch.tensor([-3., -1., 1., 3.]), 4: torch.tensor([-1., 1.])}
for shape, snr, Ns, B, ms in (('x16', 20.0, 32, 16, ['abl_colt_16_0.4_0.3_32', 'abl_colk_0_32', 'abl_dimt_0.4_0.3_32', 'abl_dimk_32', 'abl_symdt_0.4_0.2_32',
                                                     'abl_symdk_32', 'abl_sas_4_32', 'abl_sa2_32', 'abl_ptt_cyc_1.2_0.05_32', 'abl_ptc_32', 'abl_ptf_32', 'kbest8', 'kbest128']),
                              ('x32', 22.0, 8, 4, ['abl_colk_32_8', 'abl_ptcp_8', 'abl_qdimk_8', 'abl_sas_2_8']),
                              ('q32', 14.0, 8, 16, ['abl_ptfp_8', 'abl_ptt_fl_0.6_0.15_8'])):
    s = apx.SHAPES[shape]
    b = apx.draw(9700, snr, 1, B, s['nt'], s['M'])
    for m in ms:
        gs = torch.Generator(device='cuda'); gs.manual_seed(3)
        try:
            lh, dg, info = apx.detect(m, b, shape, gs, ctx)
            good = bool(torch.isin(lh, lv[s['M']].to(lh.device)).all())
            print(shape, m, 'OK' if good else 'BAD LEVELS', int(apx.biterr_per_use(b, lh).sum()), flush=True)
            ok &= good
        except Exception as e:
            print(shape, m, 'FAIL', repr(e), flush=True); ok = False
print('ALL PASS' if ok else 'SOME FAIL')
