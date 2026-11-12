#!/usr/bin/env python3
"""A5.12 analysis (PROTOCOL_A512.md sections 3-5). No GPU. Usage: analyze_a512.py ROOT REF_ROOT
ROOT = a512/results (hostA); REF_ROOT = hostB's results, read-only through <SCRATCH_MOUNT>. Ratio = parallel trial / (i) of
bit errors on batch-aligned common uses, paired cluster bootstrap (a56an.boot_ratio), exact McNemar, d_true check, as analyze_a55.py."""
import glob, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

ROOT, REF = sys.argv[1], sys.argv[2]
PT = {'P1': ('x16', 20.0, 32, 'mdiane32'), 'P2': ('x32', 22.0, 8, 'mdiane8'), 'P3': ('q32', 14.0, 8, 'mdiane8')}
CS = (5, 3, 2)
OLD = {'P1': dict(equal_cycles=1.40, equal_cycles_a52=1.53, equal_flips=1.17, equal_flips_a52=0.96),
       'P2': dict(equal_cycles=14.0, equal_flips=1.77), 'P3': dict(equal_cycles=2500, equal_flips=415)}
PRED = {('P1', 5): (0.95, 1.2), ('P1', 3): (0.7, 1.0), ('P1', 2): (0.6, 0.95), ('P2', 5): (2, 5), ('P2', 3): (1.2, 2.0),
        ('P2', 2): (0.9, 1.6), ('P3', 5): (300, 1000), ('P3', 3): (30, 300), ('P3', 2): (5, 100)}


def load(d):
    fs = sorted(glob.glob(os.path.join(d, 'b*.npz')))
    if not fs:
        raise SystemExit('missing ' + d)
    idx = [int(os.path.basename(f)[1:6]) for f in fs]
    if idx != list(range(len(fs))):
        raise SystemExit('non-contiguous batches in ' + d)
    zs = [np.load(f, allow_pickle=False) for f in fs]
    return dict(biterr=[z['biterr'].astype(np.int64) for z in zs], sizes=[len(z['biterr']) for z in zs],
                err_idx=[z['err_idx'] for z in zs], d_true=[z['d_true'] for z in zs])


def flat(r, nb=None):
    return np.concatenate(r['biterr'][:nb])


def nb_common(a, b):
    n = 0
    for x, y in zip(a['sizes'], b['sizes']):
        if x != y:
            break
        n += 1
    return n


def aligned(a, b, nb):
    checked = 0
    for i in range(nb):
        ia, ib = list(a['err_idx'][i]), list(b['err_idx'][i])
        for u in sorted(set(ia) & set(ib)):
            if not np.array_equal(a['d_true'][i][ia.index(u)], b['d_true'][i][ib.index(u)]):
                return False, checked
            checked += 1
    return True, checked


def pair(a, b):
    nb = nb_common(a, b)
    x, y = flat(a, nb), flat(b, nb)
    r, lo, hi = AN.boot_ratio(x, y)
    p, oa, ob = AN.mcnemar(x, y)
    ok, nchk = aligned(a, b, nb)
    return dict(uses=len(x), ratio=r, lo=lo, hi=hi, mcnemar_p=p, only_pt=oa, only_ref=ob, err_pt=int((x > 0).sum()),
                err_ref=int((y > 0).sum()), bit_pt=int(x.sum()), bit_ref=int(y.sum()), aligned=ok, aligned_checked=nchk)


def term(q):
    return 'pt_worse' if q['lo'] > 1 else ('pt_better' if q['hi'] < 1 else 'no_detected_difference')


sel = json.load(open(os.path.join(ROOT, 'a512_sel.json')))
out = dict(protocol='PROTOCOL_A512.md sha256 5dab3ffd927be94a9bd04f79f2783fe9d6c1c43fd83b4f467e27de29401076cc',
           written=time.strftime('%Y-%m-%d %H:%M:%S %Z'), picks={k: {kk: vv for kk, vv in v.items() if kk != 'cells'} for k, v in sel.items()},
           cells={k: v['cells'] for k, v in sel.items()}, context_A5d_A52=OLD, points={}, predictions={})
for pt, (sh, snr, Ns, refm) in PT.items():
    ref = load(os.path.join(REF, 'abl', sh, refm, 'snr_%05.2f' % snr))
    out['points'][pt] = {}
    for c in CS:
        d = os.path.join(ROOT, 'abl', sh, 'abl_pt12c%d_%d' % (c, Ns), 'snr_%05.2f' % snr)
        if not os.path.exists(os.path.join(d, 'done.json')):
            out['points'][pt]['c%d' % c] = None
            continue
        q = pair(load(d), ref)
        q['term'] = term(q)
        q['done'] = json.load(open(os.path.join(d, 'done.json')))
        out['points'][pt]['c%d' % c] = q
        lo_, hi_ = PRED[(pt, c)]
        out['predictions']['%s c=%d ratio in %g-%g' % (pt, c, lo_, hi_)] = bool(lo_ <= q['ratio'] <= hi_)
t5 = {pt: (out['points'][pt].get('c5') or {}).get('term') for pt in PT}
if all(v == 'pt_worse' for v in t5.values()):
    row = 'row 1: parallel trial worse at P1-P3 even at c = 5'
elif any(v == 'pt_better' for v in t5.values()):
    row = 'row 3: parallel trial better at ' + ', '.join(p for p, v in t5.items() if v == 'pt_better') + ' at c = 5'
elif t5['P1'] == 'no_detected_difference' and t5['P2'] == 'pt_worse' and t5['P3'] == 'pt_worse':
    row = 'row 2: P1 no detected difference at c = 5, P2/P3 worse'
else:
    row = 'other (not in the section 4 table; state each term): ' + json.dumps(t5)
out['section4_row_c5'] = row
json.dump(out, open(os.path.join(ROOT, 'a512_analysis.json'), 'w'), indent=1)
print('A5.12 analysis', out['written'])
for k, v in out['picks'].items():
    print('  pick %s: T0 %g T1 %g (%s) bit_err %d vec_err %d corner %s' % (k, v['T0'], v['T1'], v['source'], v['bit_err'], v['vec_err'], v['corner']))
for pt in PT:
    for c in CS:
        q = out['points'][pt]['c%d' % c]
        if q is None:
            print('  %s c=%d: not done' % (pt, c)); continue
        print('  %s c=%d: %.3f [%.3f, %.3f] %s  McNemar p %.2g (%d/%d)  uses %d  aligned %s (%d)' % (
            pt, c, q['ratio'], q['lo'], q['hi'], q['term'], q['mcnemar_p'], q['only_pt'], q['only_ref'], q['uses'], q['aligned'], q['aligned_checked']))
print('  section 4:', row)
print('  predictions:', json.dumps(out['predictions']))
