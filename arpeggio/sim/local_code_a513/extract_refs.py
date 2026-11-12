#!/usr/bin/env python3
"""A5.13 (PROTOCOL_A513.md section 5): copy the saved per-use bit errors and counters that A5.13 pairs with, batch by batch, into one
file. Read-only on the results; CPU only. Usage (hostB): extract_refs.py OUT.npz"""
import glob
import json
import os
import sys

import numpy as np

R = '<SCRATCH>/ap_ber_20261024/results'
SETS = {   # name: (directories (chunks merged), first batch, last batch + 1, uses per batch)
    'P1_prod': (['a56/X3P/x16/prod_fx_xs_32/snr_20.00'], 0, 200, 2000),
    'P1_float_fa': (['a55/abl/x16/abl_far_64_0.1_0.1_0_rand_32/snr_20.00'], 0, 14, 2000),
    'P1_float_ap': (['abl/x16/mdiane32/snr_20.00', 'a56/X3F/x16/a56_128_0.3_0.3_0.4_0_alt_32/snr_20.00'], 0, 198, 2000),   # float (i); X3F continues it
    'P2_prod': (['a56/X3P/x32/prod_fx_xs_8/snr_22.00'], 0, 300, 1000),
    'P2_float_fa': (['a55/abl/x32/abl_far_32_0.1_0.1_0_rand_8/snr_22.00'], 0, 43, 1000),
    'P2_float_ap': (['abl/x32/mdiane8/snr_22.00', 'a56/X3F/x32/a56_128_0.3_0.3_0.4_0_alt_8/snr_22.00'], 0, 300, 1000),
    'P4_prod': (['a56/X3P/x64/prod_fx_xs_8/snr_22.00'], 0, 600, 500),
    'P4_float_fa': (sorted(glob.glob(os.path.join(R, 'a58/held*/x64/abl_far_64_0.1_0.1_0_bal_8/snr_22.00'))), 0, 600, 500),
    'P4_float_ap': (['a56/X64F/x64/a56_128_0.3_0.3_0.4_0_alt_8/snr_22.00'], 0, 600, 500),
}
out, meta = {}, {}
for name, (dirs, b0, b1, B) in SETS.items():
    files = {}
    for d in dirs:
        d = d if d.startswith('/') else os.path.join(R, d)
        for f in glob.glob(os.path.join(d, 'b*.npz')):
            bi = int(os.path.basename(f)[1:6])
            assert bi not in files, (name, bi)
            files[bi] = f
    infos = []
    for bi in range(b0, b1):
        z = np.load(files[bi], allow_pickle=False)
        x = z['biterr']
        assert len(x) == B, (name, bi, len(x))
        out['%s/b%05d' % (name, bi)] = x.astype(np.uint8)
        infos.append(json.loads(str(z['info'])))
    meta[name] = dict(dirs=dirs, b0=b0, b1=b1, B=B, info=infos)
    print(name, b1 - b0, 'batches', sum(int((out['%s/b%05d' % (name, i)] > 0).sum()) for i in range(b0, b1)), 'erroneous uses', flush=True)
out['meta'] = np.array(json.dumps(meta))
np.savez_compressed(sys.argv[1], **out)
print('saved', sys.argv[1])
