#!/usr/bin/env python3
"""A5.10 analysis (PROTOCOL_A510.md sections 5 and 8), written before any A5.10 run. Usage: analyze_a510.py RUNS_DIR NEG.txt OUT.json"""
import json, os, sys
RUNS, NEG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
D = {'p1': 32, 'p2': 64}
ENG, AS = ('v14', 'fa', 'fx2', 'fx3'), (1, 4, 6, 8)
XFP_HELD = {'p1': 0.6326, 'p2': 0.4110}            # protocol section 2: flips.json and A5.5's ref_cost, existing B = 1 picks
LANE_BITS = {'v14': 70, 'fa': 71, 'fx2': 98, 'fx3': 98}   # per lane per context (section 3), structural only
CTX_BITS = 295                                       # per-context scalars (st .. cfa1), approximate


def load(pt, eng, A):
    stim = pt + ('ap' if eng == 'v14' else 'fa')
    p = os.path.join(RUNS, '%s_%s_a%d_d%d' % (stim, eng, A, D[pt]), 'cycles.json')
    return json.load(open(p)) if os.path.exists(p) else None


def mean(v):
    return sum(v) / len(v)


res, bad, missing = {}, [], []
for pt in ('p1', 'p2'):
    C, J = {}, {}
    for e in ENG:
        for A in AS:
            j = load(pt, e, A)
            if j is None:
                missing.append('%s %s A=%d' % (pt, e, A)); continue
            J[(e, A)] = j
            if not j['all_pass']:
                bad.append('%s %s A=%d' % (pt, e, A))
            C[(e, A)] = {K: v['cycles_per_anneal'] for K, v in j['per_K'].items()}
    Ks = ('1', '2', '3')
    have = lambda e, A: (e, A) in C
    r = dict(cycles={'%s/A%d' % k: v for k, v in C.items()})
    # RTL over model per engine and A (v14: L + F; fa: tests + F; fx: S P + F, S P = decision-port tests T_rtl)
    rm = {}
    for (e, A), j in J.items():
        rm['%s/A%d' % (e, A)] = {K: v['cycles_per_anneal'] / ((v['L'] + v['F']) if e == 'v14' else (v['tests'] + v['F']) if e == 'fa' else (v['T_rtl'] + v['F']))
                                 for K, v in j['per_K'].items()}
    r['rtl_over_model'] = rm
    g = {}
    for fx in ('fx2', 'fx3'):
        for A in AS:
            if have(fx, A) and have('fa', A):
                g['%s/A%d' % (fx, A)] = mean([C[(fx, A)][K] / C[('fa', A)][K] for K in Ks])
    r['g'] = g
    iso = {}
    for fx in ('fx2', 'fx3'):
        fa_as = [a for a in (4, 6, 8) if have('fa', a)]
        if have(fx, 4) and fa_as:
            per = {K: C[(fx, 4)][K] / min(C[('fa', a)][K] for a in fa_as) for K in Ks}
            iso[fx] = dict(value=mean(list(per.values())), per_K=per, best_fa_A={K: min(fa_as, key=lambda a: C[('fa', a)][K]) for K in Ks})
    r['iso'] = iso
    x = {}
    for e in ENG:
        for A in AS:
            if have(e, A) and have('v14', A):
                x['%s/A%d' % (e, A)] = mean([C[(e, A)][K] / C[('v14', A)][K] for K in Ks])
    r['x_rtl_vs_v14_same_A'] = x
    if have('fx3', 4) and have('v14', 4):
        fxp = J[('fx3', 4)]['per_K']; ap = J[('v14', 4)]['per_K']
        x_stim = mean([(fxp[K]['T_rtl'] + fxp[K]['F']) / (ap[K]['L'] + ap[K]['F']) for K in Ks])
        r['x_Fp_stim'] = x_stim
        r['x_hat'] = {}
        for fx in ('fx2', 'fx3'):
            for A in AS:
                k = '%s/A%d' % (fx, A)
                if k in x:
                    r['x_hat'][k] = dict(c=x[k] / x_stim, x_hat=XFP_HELD[pt] * x[k] / x_stim)
    lat = {}
    for e in ENG:
        if have(e, 1):
            lat[e] = {K: J[(e, 1)]['per_K'][K].get('lat_per_anneal') for K in Ks}
    r['latency_A1'] = lat
    r['latency_ratio_A1'] = {('%s/%s' % (a, b)): mean([lat[a][K] / lat[b][K] for K in Ks])
                             for a in ('fx2', 'fx3') for b in ('fa', 'v14') if a in lat and b in lat}
    r['cycle_offset_A1'] = {e: J[(e, 1)].get('cycle_offset_A1') for e in ENG if have(e, 1)}
    r['register_bits'] = {'%s/A%d' % (e, A): A * (LANE_BITS[e] * D[pt] + CTX_BITS) for e in ENG for A in AS}
    a_ok = g.get('fx3/A4') is not None and g['fx3/A4'] <= 0.80
    b_ok = 'fx3' in iso and iso['fx3']['value'] <= 0.85
    r['criteria'] = dict(a_g4_fx3=g.get('fx3/A4'), a_ok=a_ok, b_iso_fx3=iso.get('fx3', {}).get('value'), b_ok=b_ok)
    r['fa8_vs_fa4'] = mean([C[('fa', 8)][K] / C[('fa', 4)][K] for K in Ks]) if have('fa', 8) and have('fa', 4) else None
    res[pt] = r
neg = {}
for line in open(NEG):
    a = line.split()
    if a and a[0] == 'NEG':                      # NEG name check_exit=N tb=TB_DONE|TB_CAP_HIT
        kv = dict(t.split('=') for t in a[2:])
        neg[a[1]] = dict(kv, failed_as_required=(kv.get('check_exit') != '0') or (kv.get('tb') == 'TB_CAP_HIT'))
res['negative_controls'] = neg
neg_ok = len(neg) == 2 and all(v['failed_as_required'] for v in neg.values())
if bad or missing or not neg_ok:
    res['outcome'] = 'stopped: ' + '; '.join(['failed check ' + ', '.join(bad)] * bool(bad) + ['missing ' + ', '.join(missing)] * bool(missing) +
                                              ['negative control passed or missing'] * (not neg_ok))
else:
    both = {pt: res[pt]['criteria']['a_ok'] and res[pt]['criteria']['b_ok'] for pt in ('p1', 'p2')}
    res['outcome'] = 'GO' if all(both.values()) else ('GO-P2' if both['p2'] else 'NO-GO')
json.dump(res, open(OUT, 'w'), indent=1)
for pt in ('p1', 'p2'):
    r = res[pt]
    print(pt, 'criteria', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r['criteria'].items()})
    print('   g', {k: round(v, 3) for k, v in r['g'].items()})
    print('   iso', {k: round(v['value'], 3) for k, v in r['iso'].items()}, 'best FA A per K', r['iso'].get('fx3', {}).get('best_fa_A'))
    print('   x vs v14 (same A)', {k: round(v, 3) for k, v in r['x_rtl_vs_v14_same_A'].items()})
    print('   x_hat', {k: round(v['x_hat'], 3) for k, v in r.get('x_hat', {}).items()}, 'x_Fp_stim', round(r.get('x_Fp_stim', 0), 3))
    print('   latency A=1 ratios', {k: round(v, 3) for k, v in r['latency_ratio_A1'].items()}, 'offsets', r['cycle_offset_A1'])
    print('   fa(8)/fa(4)', None if r['fa8_vs_fa4'] is None else round(r['fa8_vs_fa4'], 3))
    print('   rtl/model', {k: [round(x, 2) for x in v.values()] for k, v in r['rtl_over_model'].items()})
print('negative controls', neg)
print('outcome', res['outcome'])
