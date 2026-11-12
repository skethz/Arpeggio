import torch, apx, mimo, time
ctx = apx.Ctx({})
for sh, snr, ms in (('x16', 20.0, ['mdiahck64', 'amb_om2_64', 'amb_x0sd_64', 'amb_floor_64', 'sic', 'sicc', 'mdiane64']), ('q32', 13.0, ['mdiahck64', 'amb_x0sd_64'])):
    s = apx.SHAPES[sh]; b = apx.draw(9500, snr, 0, 200, s['nt'], s['M'])
    for m in ms:
        gs = torch.Generator(device='cuda'); gs.manual_seed(3); t = time.time()
        lh, dg, info = apx.detect(m, b, sh, gs, ctx)
        print(sh, m, int(apx.biterr_per_use(b, lh).sum()), info.get('anneals'), round(time.time() - t, 1), flush=True)
# omega=None path equals mimo.mdi with the AHC kernel solver
