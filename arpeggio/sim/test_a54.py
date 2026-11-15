#!/usr/bin/env python3
"""A5.4 development checks (dev seed 1000, 200 uses). abl_anel_128_<Ns> must equal mdichord<Ns> for the same solver seed;
another Sk must differ and still return constellation levels."""
import torch, arpx, runner_a54  # noqa: F401
ctx = arpx.Ctx({})
ok = True
for shape, snr, Ns, B in (('x16', 20.0, 32, 200), ('x32', 22.0, 8, 100)):
    s = arpx.SHAPES[shape]
    b = arpx.draw(1000, snr, 50, B, s['nt'], s['M'])
    z, _, _ = arpx.mimo.mmse(b)
    out = {}
    for m in ('mdichord%d' % Ns, 'abl_anel_128_%d' % Ns, 'abl_anel_64_%d' % Ns):
        g = torch.Generator(device='cuda'); g.manual_seed(12345)
        lh, _, info = arpx.detect(m, b, shape, g, ctx, z=z)
        out[m] = (lh.clone(), info['anneals'])
    same = torch.equal(out['mdichord%d' % Ns][0], out['abl_anel_128_%d' % Ns][0])
    diff = out['mdichord%d' % Ns][1] != out['abl_anel_64_%d' % Ns][1]   # few errors at 200 uses, so outputs can coincide; the anneal count shows the solver changed
    lv = out['abl_anel_64_%d' % Ns][0]
    levels = bool(torch.all((lv.abs() == 1) | (lv.abs() == 3)))
    print(shape, 'Sk 128 identical to mdichord:', same, '| Sk 64 solver differs:', diff, '| levels:', levels, '| anneals', out['mdichord%d' % Ns][1], out['abl_anel_64_%d' % Ns][1], flush=True)
    ok = ok and same and diff and levels
print('ALL PASS' if ok else 'FAIL')
