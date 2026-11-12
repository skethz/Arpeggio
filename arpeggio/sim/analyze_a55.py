#!/usr/bin/env python3
"""A5.5 analysis, PROTOCOL_A55.md section 9 (written 6 Nov 2026 after A5.5 completed; the rule and terms were fixed at freeze, 5 Nov 01:40).
No GPU. Usage: analyze_a55.py RESULTS_DIR   (RESULTS_DIR = .../results; reads a55/select.json, a55/flips.json, tuned_a52.json)
Writes RESULTS_DIR/a55/analysis.json.

Per held-out pick: BER, paired ratio pick/(i) on the batch-aligned common prefix of seed 102 (cluster bootstrap over uses, a56an.boot_ratio,
and exact McNemar, as A5/A5.4), the same-draws check, and x per K under each model from the section 7 calibration (seed 1000, batch 50):
  E    = S N + F_SA                       (fam; Eq. (4) as printed)
  F    = tests + F_SA                     (fam = F-M, far = F-R)
  Antiphase picks: L + F, L = 128 * 2K
  ref  = L + phi_K L                      ((i), tuned_a52 flip_phi)
  latency: (3 tests + 2 F_SA) / (3 L + F_ref + n1), n1 not counted; reported for n1 = 0 and n1 = min(L, F_ref)
Mean over K is arithmetic, as the budget selection (a55_plan.x_of). Terms (section 9): Antiphase leads if lo > 1, SA leads if hi < 1."""
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a56an as AN  # noqa: E402

RES = sys.argv[1]
A55 = os.path.join(RES, 'a55')
SEL = json.load(open(os.path.join(A55, 'select.json')))
FL = json.load(open(os.path.join(A55, 'flips.json')))
PHI = json.load(open(os.path.join(RES, 'tuned_a52.json')))['flip_phi']
PT = {'P1': dict(sh='x16', snr=20.0, Ns=32, bpu=64),
      'P2': dict(sh='x32', snr=22.0, Ns=8, bpu=128),
      'P3': dict(sh='q32', snr=14.0, Ns=8, bpu=64)}
BUDGETS = ('0.5', '1', '2', '3')
MODELS = ('E', 'F-M', 'F-R')


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
    """Leading batches with equal sizes; draws are seeded by (seed, SNR, batch index, batch size), so a batch of another size is other draws."""
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
    """Ratio a/b of bit errors on common uses."""
    nb = nb_common(a, b)
    x, y = flat(a, nb), flat(b, nb)
    r, lo, hi = AN.boot_ratio(x, y)
    p, oa, ob = AN.mcnemar(x, y)
    ok, nchk = aligned(a, b, nb)
    return dict(uses=len(x), ratio=r, lo=lo, hi=hi, mcnemar_p=p, only_first=oa, only_second=ob,
                err_first=int((x > 0).sum()), err_second=int((y > 0).sum()), bit_first=int(x.sum()), bit_second=int(y.sum()),
                aligned=ok, aligned_checked=nchk)


def term(q):
    if q is None or q['lo'] is None:
        return None
    return 'antiphase_leads' if q['lo'] > 1 else ('sa_leads' if q['hi'] < 1 else 'no_detected_difference')


def parse(m):
    a = m.split('_')
    arm = a[1]
    if arm in ('fam', 'far'):
        return arm, int(a[2])
    return arm, None


def ref_cost(sh, K):
    L = 128 * 2 * K
    return L, PHI[sh][str(K)] * L


def xs(m, sh):
    """x per K under each model from the section 7 calibration; None for parallel trial (A5's budgets)."""
    arm, S = parse(m)
    if arm == 'ptb' or m not in FL:
        return None
    out = {}
    for K, v in FL[m].items():
        if K not in PHI[sh]:                                               # P3 has a reference cost at K = 1 only (PROTOCOL_A55 section 3)
            continue
        L, Fr = ref_cost(sh, int(K))
        ref = L + Fr
        F = v['flips'] / v['anneals']
        if arm in ('fam', 'far'):
            t = v['tests'] / v['anneals']
            cF = t + F
            lat = 3 * t + 2 * F
            out[K] = dict(F=F, tests=t, N=v['N'], x_E=(S * v['N'] + F) / ref, x_F=cF / ref,
                          x_lat_n1_0=lat / (3 * L + Fr), x_lat_n1_max=lat / (3 * L + Fr + min(L, Fr)))
            out[K]['lat_over_F'] = [out[K]['x_lat_n1_max'] / out[K]['x_F'], out[K]['x_lat_n1_0'] / out[K]['x_F']]
        else:                                                              # Antiphase arm
            st = v['steps'] / v['anneals']
            out[K] = dict(F=F, L=st, x_E=(st + F) / ref, x_F=(st + F) / ref)
    mean = {k: float(np.mean([out[K][k] for K in out])) for k in ('x_E', 'x_F')}
    return dict(per_K=out, mean=mean)


def stagea_x(m, sh):
    """x the selector used: stage A counts on seed 1000 (a55_plan.counts / x_of)."""
    arm, S = parse(m)
    d = os.path.join(A55, 'tunea', sh, m)
    fs = glob.glob(os.path.join(d, 'snr_*', 'b*.npz'))
    if arm not in ('fam', 'far') or not fs:
        return None
    tot = {}
    for f in sorted(fs):
        z = np.load(f, allow_pickle=False)
        for K, v in json.loads(str(z['info'])).get('count', {}).items():
            t = tot.setdefault(K, dict(flips=0.0, tests=0, anneals=0, N=v['N']))
            t['flips'] += v['flips']; t['tests'] += v.get('tests', 0); t['anneals'] += v['anneals']
    xe, xf = [], []
    for K, v in tot.items():
        if K not in PHI[sh]:
            continue
        L, Fr = ref_cost(sh, int(K))
        F, t = v['flips'] / v['anneals'], v['tests'] / v['anneals']
        xe.append((S * v['N'] + F) / (L + Fr)); xf.append((t + F) / (L + Fr))
    return dict(x_E=float(np.mean(xe)), x_F=float(np.mean(xf)))


out = dict(note='A5.5 analysis, PROTOCOL_A55.md section 9; exploratory; modeled cycles only (no timing, area or energy); held-out seed 102; '
                'x from the section 7 calibration (seed 1000, batch 50), mean over K arithmetic; ratio = pick / (i) on batch-aligned common uses.',
           points={})
cache = {}


def run(pt, m):
    p = PT[pt]
    k = (pt, m)
    if k not in cache:
        cache[k] = load(os.path.join(A55, 'abl', p['sh'], m, 'snr_%05.2f' % p['snr']))
    return cache[k]


for pt, p in PT.items():
    ref = load(os.path.join(RES, 'abl', p['sh'], 'mdiane%d' % p['Ns'], 'snr_%05.2f' % p['snr']))
    refb = flat(ref)
    held = SEL['held'][pt]
    apm = SEL['ap']['%s/ape' % pt]['method']
    picks = {}
    for m in held:
        r = run(pt, m)
        b = flat(r)
        dn = json.load(open(os.path.join(A55, 'abl', p['sh'], m, 'snr_%05.2f' % p['snr'], 'done.json')))
        row = dict(method=m, uses=len(b), err_uses=int((b > 0).sum()), bit_err=int(b.sum()), ber=float(b.sum()) / (len(b) * p['bpu']),
                   capped=bool(dn.get('capped', False)), vs_i=pair(r, ref), x=xs(m, p['sh']), x_stage_a=stagea_x(m, p['sh']))
        if m != apm:
            row['vs_ap_pick'] = pair(r, run(pt, apm))                    # secondary
        picks[m] = row
    budget = {}
    for mod in MODELS:
        for B in BUDGETS:
            key = '%s/%s/%s' % (pt, mod, B)
            if key not in SEL['budget']:
                budget['%s/%s' % (mod, B)] = None
                continue
            m = SEL['budget'][key]['method']
            q = picks[m]['vs_i']
            xm = picks[m]['x']['mean'] if picks[m]['x'] else None
            budget['%s/%s' % (mod, B)] = dict(method=m, ratio=q['ratio'], lo=q['lo'], hi=q['hi'], mcnemar_p=q['mcnemar_p'], uses=q['uses'],
                                              term=term(q), x_E=xm and xm['x_E'], x_F=xm and xm['x_F'], x_stage_a=picks[m]['x_stage_a'])
    per_s = {}
    for k, v in SEL['per_s'].items():
        if not k.startswith(pt + '/') or '/ape/' in k:                  # the Antiphase stage-A best is not a held-out job (a55_plan)
            continue
        m = v['method']
        q = picks[m]['vs_i']
        xm = picks[m]['x']['mean'] if picks[m]['x'] else None
        per_s[k[len(pt) + 1:]] = dict(method=m, ratio=q['ratio'], lo=q['lo'], hi=q['hi'], term=term(q), x_E=xm and xm['x_E'],
                                      x_F=xm and xm['x_F'], corner=k in SEL['corner'])
    others = {}
    for k, v in list(SEL['ap'].items()) + list(SEL['pt'].items()):
        if k.startswith(pt + '/'):
            q = picks[v['method']]['vs_i']
            others[k[len(pt) + 1:]] = dict(method=v['method'], ratio=q['ratio'], lo=q['lo'], hi=q['hi'], term=term(q))
    fz = 'abl_ape_0.3_0.3_0.4_bal_%d' % p['Ns']
    q = picks[fz]['vs_i']
    others['ape_bal_frozen'] = dict(method=fz, ratio=q['ratio'], lo=q['lo'], hi=q['hi'], term=term(q))
    out['points'][pt] = dict(ref=dict(method='mdiane%d' % p['Ns'], uses=len(refb), err_uses=int((refb > 0).sum()), bit_err=int(refb.sum()),
                                      ber=float(refb.sum()) / (len(refb) * p['bpu'])),
                             budget=budget, per_s=per_s, others=others, picks=picks)

# section 9 classes and rules (P1, P2)
V = {}
for pt in ('P1', 'P2'):
    bud = out['points'][pt]['budget']
    e, fr = bud.get('E/1'), bud.get('F-R/1')
    le = e is not None and e['term'] == 'antiphase_leads'
    lr = fr is not None and fr['term'] == 'antiphase_leads'
    V[pt] = 'Both' if le and lr else ('E-only' if le else 'None')
cls = [V['P1'], V['P2']]
if cls == ['Both', 'Both']:
    row = 'Both at P1 and P2'
elif 'None' not in cls:
    row = 'E-only at one or both, None at neither'
else:
    row = 'None at either'
le1 = []
for pt in ('P1', 'P2'):
    for mod in ('E', 'F-R'):
        for B in BUDGETS:
            v = out['points'][pt]['budget'].get('%s/%s' % (mod, B))
            if v is not None and v['ratio'] <= 1:
                le1.append('%s %s B=%s: %.3f [%.3f, %.3f]' % (pt, mod, B, v['ratio'], v['lo'], v['hi']))
sa_leads = ['%s %s B=%s' % (pt, mod, B) for pt in ('P1', 'P2') for mod in ('E', 'F-R') for B in BUDGETS
            if (out['points'][pt]['budget'].get('%s/%s' % (mod, B)) or {}).get('term') == 'sa_leads']
out['verdict'] = dict(class_B1=V, outcome_row=row, antiphase_wins_leaves_table_I=bool(le1), estimates_le_1=le1, sa_leads_at=sa_leads)

# section 10 predictions, where computable
pred = {}
def bq(pt, mod, B='1'):
    return out['points'][pt]['budget'].get('%s/%s' % (mod, B))
for pt, mod, lo_, hi_ in (('P1', 'E', 1.2, 2.5), ('P2', 'E', 3, 12), ('P1', 'F-R', 0.6, 1.5), ('P2', 'F-R', 0.8, 3)):
    v = bq(pt, mod)
    pred['%s %s B=1 in %g-%g' % (pt, mod, lo_, hi_)] = None if v is None else bool(lo_ <= v['ratio'] <= hi_)
    pred['%s %s B=1 term' % (pt, mod)] = None if v is None else v['term']
v = bq('P2', 'E')
if v:
    pred['P2 E below 10'] = v['ratio'] < 10; pred['P2 E below 5'] = v['ratio'] < 5
for pt in ('P1', 'P2'):
    for mod in ('E', 'F-R'):
        pred['%s %s estimate <= 1 at some B <= 3' % (pt, mod)] = any((bq(pt, mod, B) or {}).get('ratio', 9) <= 1 for B in BUDGETS)
old1 = {'P1': 'abl_sao_1_32', 'P2': 'abl_sas_1_8'}
for pt, om in old1.items():
    p = PT[pt]
    d = os.path.join(RES, 'abl', p['sh'], om, 'snr_%05.2f' % p['snr'])
    if os.path.isdir(d):
        q = pair(load(d), run(pt, SEL['per_s']['%s/fam/1' % pt]['method']))
        pred['%s S=1 re-tuned cuts BER >= 3x vs T=2.4' % pt] = dict(holds=bool(q['ratio'] >= 3), old_over_new=q['ratio'], lo=q['lo'], hi=q['hi'])


def best_start(pt, arm, S):
    p = PT[pt]
    best = {}
    for f in glob.glob(os.path.join(A55, 'tunea', p['sh'], 'abl_%s_%d_*' % (arm, S), 'snr_*', 'done.json')):
        d = json.load(open(f))
        st = d['method'].split('_')[-2]
        best[st] = min(best.get(st, 9), d['ber'])
    return best


bal = {}
for pt in PT:
    for arm, Ss in (('fam', (1, 2, 3, 4, 32, 64, 128)), ('far', (4, 32, 64, 128))):
        for S in Ss:
            b = best_start(pt, arm, S)
            if 'rand' in b and 'bal' in b and b['bal'] > 0:
                bal['%s/%s/%d' % (pt, arm, S)] = dict(rand=b['rand'], bal=b['bal'], rand_over_bal=b['rand'] / b['bal'])
pred['bal vs rand, stage A best cells'] = bal
for pt in ('P1', 'P2', 'P3'):
    o = out['points'][pt]['others']
    pred['%s Antiphase bal frozen in 0.8-1.2 of (i)' % pt] = bool(0.8 <= o['ape_bal_frozen']['ratio'] <= 1.2)
pred['P2 Antiphase pick <= 0.8'] = out['points']['P2']['others']['ape']['ratio'] <= 0.8
pred['P1 Antiphase pick CI covers 1'] = bool(out['points']['P1']['others']['ape']['lo'] <= 1 <= out['points']['P1']['others']['ape']['hi'])
for pt, old in (('P2', 14), ('P3', 2500)):
    v = out['points'][pt]['others'].get('ptb/cyc')
    if v:
        pred['%s parallel trial bal cyc >= 3x better than %g' % (pt, old)] = dict(holds=bool(v['ratio'] <= old / 3), ratio=v['ratio'])
v = out['points']['P2']['others'].get('ptb/cyc')
if v:
    pred['P2 parallel trial still behind (i)'] = v['term'] == 'antiphase_leads'
fmfr = {}
for pt in ('P1', 'P2'):
    for B in BUDGETS:
        a, b = bq(pt, 'F-M', B), bq(pt, 'F-R', B)
        if a and b:
            q = pair(run(pt, a['method']), run(pt, b['method']))
            fmfr['%s/%s' % (pt, B)] = dict(fm_over_fr=q['ratio'], lo=q['lo'], hi=q['hi'], within_1_5=bool(1 / 1.5 <= q['ratio'] <= 1.5))
pred['F-M and F-R within 1.5x at the same budget'] = fmfr
lat = []
for pt in PT:
    for m, r in out['points'][pt]['picks'].items():
        if r['x'] and parse(m)[0] in ('fam', 'far'):
            for K, v in r['x']['per_K'].items():
                lat += v['lat_over_F']
pred['x_lat/x_F range over picks and K (n1 bounds)'] = [min(lat), max(lat)] if lat else None
out['predictions'] = pred

# every stage A and B cell, pruned and corner cells (reported, section 9)
cells = {}
for st in ('probe', 'tunea', 'tuneb'):
    for f in glob.glob(os.path.join(A55, st, '*', '*', 'snr_*', 'done.json')):
        d = json.load(open(f))
        cells.setdefault(st, []).append(dict(shape=d['shape'], method=d['method'], uses=d['uses'], vec_err=d['vec_err'], bit_err=d['bit_err'], ber=d['ber']))
out['cells'] = {k: sorted(v, key=lambda r: (r['shape'], r['method'])) for k, v in cells.items()}
out['pruned'], out['corner'] = SEL['pruned'], SEL['corner']
json.dump(out, open(os.path.join(A55, 'analysis.json'), 'w'), indent=1)

# print
for pt, d in out['points'].items():
    r = d['ref']
    print('%s (i) %s uses %d err %d BER %.3g' % (pt, r['method'], r['uses'], r['err_uses'], r['ber']))
    for k, v in d['budget'].items():
        if v is None:
            print('  %-7s none' % k); continue
        print('  %-7s %-34s x_E %.2f x_F %.2f  SA/(i) %.3f [%.3f, %.3f] p %.2g  uses %d  %s' % (
            k, v['method'], v['x_E'], v['x_F'], v['ratio'], v['lo'], v['hi'], v['mcnemar_p'], v['uses'], v['term']))
    for k, v in sorted(d['per_s'].items(), key=lambda t: (t[0].split('/')[0], int(t[0].split('/')[1]))):
        print('  S %-8s %-34s x_E %.2f x_F %.2f  %.3f [%.3f, %.3f] %s%s' % (k, v['method'], v['x_E'], v['x_F'], v['ratio'], v['lo'], v['hi'], v['term'],
                                                                             ' corner' if v['corner'] else ''))
    for k, v in d['others'].items():
        print('  %-14s %-30s %.3f [%.3f, %.3f] %s' % (k, v['method'], v['ratio'], v['lo'], v['hi'], v['term']))
    bad = [m for m, r in d['picks'].items() if not r['vs_i']['aligned']]
    print('  aligned with (i): %s' % ('all' if not bad else 'NOT ' + ','.join(bad)))
print('VERDICT', json.dumps(out['verdict']))
print('PREDICTIONS', json.dumps(pred, default=float)[:4000])
