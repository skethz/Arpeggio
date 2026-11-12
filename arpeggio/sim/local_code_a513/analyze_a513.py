#!/usr/bin/env python3
"""A5.13 analysis (PROTOCOL_A513.md section 7), written before any held-out result. CPU only.
Pairs the fixed-point first-accept runs batch by batch with the saved runs in refs_a513.npz (same draws, same batch size), with the
estimators of A5.6/A5.8 (a56an.boot_ratio: paired cluster bootstrap, 4,000 replicates, seed 12345; a56an.mcnemar: exact, on erroneous uses).
Scopes: 'all' = every saved production (X3P) batch of the point (primary, fixed first-accept vs production Antiphase);
'matched' = the batches of the floating-point first-accept pick run (quantization check, fixed vs floating first-accept).
Usage: analyze_a513.py ROOT REFS.npz OUT.json [HOSTCHECK_ROOT]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np

import a56an as AN

POINTS = {   # point: (tag, fixed-point method, snr, matched batches, all batches, uses per batch, bits per use, production method)
    'P1': ('x16', 'fafx_64_0.1_0.1_0_rand_32', 20.0, (0, 14), (0, 200), 2000, 64, 'prod_fx_xs_32'),
    'P2': ('x32', 'fafx_32_0.1_0.1_0_rand_8', 22.0, (0, 43), (0, 300), 1000, 128, 'prod_fx_xs_8'),
    'P4': ('x64', 'fafx_64_0.1_0.1_0_bal_8', 22.0, (0, 600), (0, 600), 500, 256, 'prod_fx_xs_8'),
}


def term(lo, hi, names=('antiphase_leads', 'sa_leads')):
    if lo is not None and lo > 1:
        return names[0]
    if hi is not None and hi < 1:
        return names[1]
    return 'no_detected_difference'


def compare(a, b, nb, names=('antiphase_leads', 'sa_leads')):
    r, lo, hi = AN.boot_ratio(a, b)
    p, nx, ny = AN.mcnemar(a, b)
    return dict(ratio=r, lo=lo, hi=hi, mcnemar_p=p, a_only=nx, b_only=ny, uses=int(len(a)), a_err_uses=int((a > 0).sum()),
                b_err_uses=int((b > 0).sum()), a_bit_err=int(a.sum()), b_bit_err=int(b.sum()),
                a_ber=float(a.sum()) / (len(a) * nb), b_ber=float(b.sum()) / (len(b) * nb), term=term(lo, hi, names))


def addcnt(acc, cnt):
    for K, v in cnt.items():
        a = acc.setdefault(K, [0, 0, 0])
        for i in range(3):
            a[i] += v[i]


def xf(cfx, cp):
    """x_F: mean over K of C_FA = (tests + flips) per anneal over production's C_AP = (L + F) per anneal."""
    kf = {K: (v[0] + v[1]) / v[2] for K, v in cfx.items() if v[2]}
    kp = {K: (v[0] + v[1]) / v[2] for K, v in cp.items() if v[2]}
    xk = {K: kf[K] / kp[K] for K in kf if K in kp}
    return (float(np.mean(list(xk.values()))) if xk else None), xk, kf, kp


def main(root, refs, outp, hostroot=None):
    z = np.load(refs, allow_pickle=False)
    meta = json.loads(str(z['meta']))
    res = dict(note=__doc__.split('\n')[0], refs=refs, points={})
    for pt, (tag, meth, snr, (m0, m1), (a0, a1), B, nb, pmeth) in POINTS.items():
        d = os.path.join(root, tag, meth, 'snr_%05.2f' % snr)
        done = set(int(f[1:6]) for f in os.listdir(d) if f.startswith('b') and f.endswith('.npz')) if os.path.isdir(d) else set()
        ia = [i for i in range(a0, a1) if i in done]
        im = [i for i in range(m0, m1) if i in done]
        r = dict(method=meth, planned_all=a1 - a0, batches_all=len(ia), planned_matched=m1 - m0, batches_matched=len(im),
                 complete=len(ia) == a1 - a0 and len(im) == m1 - m0)
        if not ia:
            res['points'][pt] = r
            continue
        fx, cfx, coef = {}, {}, dict(max_coef=0, over13=0, over15=0, subproblems=0)
        for i in ia:
            y = np.load(os.path.join(d, 'b%05d.npz' % i), allow_pickle=False)
            assert len(y['biterr']) == B
            fx[i] = y['biterr'].astype(np.int64)
            info = json.loads(str(y['info']))
            fx[(i, 'cnt')] = info['cnt']
            addcnt(cfx, info['cnt'])
            for k in ('over13', 'over15', 'subproblems'):
                coef[k] += info['coef'][k]
            coef['max_coef'] = max(coef['max_coef'], info['coef']['max_coef'])
        cat = lambda ii: np.concatenate([fx[i] for i in ii])
        ref = lambda nm, ii: np.concatenate([z['%s_%s/b%05d' % (pt, nm, i)].astype(np.int64) for i in ii])
        rng = lambda nm: range(meta['%s_%s' % (pt, nm)]['b0'], meta['%s_%s' % (pt, nm)]['b1'])
        # primary: fixed first-accept vs production Antiphase on every saved production batch
        r['fx_prod'] = compare(cat(ia), ref('prod', ia), nb)
        ip = [i for i in ia if i in rng('float_ap')]
        r['fx_float_ap'] = compare(cat(ip), ref('float_ap', ip), nb)
        r['fx_float_ap']['batches'] = len(ip)
        pinfo, pb0 = meta['%s_prod' % pt]['info'], meta['%s_prod' % pt]['b0']
        cp = {}
        for i in ia:
            addcnt(cp, pinfo[i - pb0]['cnt'])
        r['x_F_vs_prod'], r['x_F_vs_prod_per_K'], kf, kp = xf(cfx, cp)
        r['cost_per_anneal'] = dict(fx=kf, prod=kp)
        r['counters_fx'] = cfx
        r['coef'] = coef
        # quantization check and continuity, on the floating-point pick's batches
        if im:
            S, P_, F_, A_ = cat(im), ref('prod', im), ref('float_fa', im), ref('float_ap', im)
            r['matched'] = dict(fx_float_fa=compare(S, F_, nb, ('fixed_worse', 'fixed_better')), fx_prod=compare(S, P_, nb),
                                fx_float_ap=compare(S, A_, nb), float_fa_prod=compare(F_, P_, nb), float_fa_float_ap=compare(F_, A_, nb),
                                prod_float_ap=compare(P_, A_, nb))
            cpm, cfm = {}, {}
            for i in im:
                addcnt(cpm, pinfo[i - pb0]['cnt']); addcnt(cfm, fx[(i, 'cnt')])
            r['matched']['x_F_vs_prod'] = xf(cfm, cpm)[0]
        # host check (reported only): production model rerun on this host for some batches
        if hostroot:
            hd = os.path.join(hostroot, tag, pmeth, 'snr_%05.2f' % snr)
            ih = sorted(int(f[1:6]) for f in os.listdir(hd) if f.startswith('b') and f.endswith('.npz')) if os.path.isdir(hd) else []
            ih = [i for i in ih if i in rng('prod')]
            if ih:
                H = np.concatenate([np.load(os.path.join(hd, 'b%05d.npz' % i), allow_pickle=False)['biterr'].astype(np.int64) for i in ih])
                Pm = ref('prod', ih)
                r['hostcheck'] = dict(batches=len(ih), uses=int(len(H)), uses_differing=int((H != Pm).sum()), host_bit_err=int(H.sum()),
                                      saved_bit_err=int(Pm.sum()))
                ihf = [i for i in ih if i in fx]
                if ihf:
                    Hf = np.concatenate([np.load(os.path.join(hd, 'b%05d.npz' % i), allow_pickle=False)['biterr'].astype(np.int64) for i in ihf])
                    r['hostcheck']['fx_prod_same_host'] = compare(cat(ihf), Hf, nb)
                    r['hostcheck']['fx_prod_saved_same_batches'] = compare(cat(ihf), ref('prod', ihf), nb)
        res['points'][pt] = r
        q = r.get('matched', {}).get('fx_float_fa')
        print(pt, 'batches %d/%d' % (len(ia), a1 - a0), 'x_F %.3f' % r['x_F_vs_prod'],
              'fx/prod %.3f [%.3f, %.3f] %s' % (r['fx_prod']['ratio'], r['fx_prod']['lo'], r['fx_prod']['hi'], r['fx_prod']['term']),
              ('fx/float_fa %.3f [%.3f, %.3f] %s' % (q['ratio'], q['lo'], q['hi'], q['term'])) if q else '', flush=True)
    json.dump(res, open(outp, 'w'), indent=1)


if __name__ == '__main__':
    main(*sys.argv[1:5])
