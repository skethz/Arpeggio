"""Fig. 3(a,b) with A5.5's SA re-tuned per sweep count: SA series under E and under F, F-R and F-M marked apart,
the compressed series as a gray reference. Writes to out/.

(a), (b) BER relative to Chord (i) against modeled cycles per anneal relative to Chord, held-out seed 102:
    - SA re-tuned per S (per-S picks, stage A on seed 1000), cost E = S N + F_SA (Eq. (4)): filled circles, solid;
    - the same Metropolis picks under first-accept cost F = tests + F_SA (F-M, a Metropolis unit per lane): open triangles;
    - rule (2) first-accept per-S picks under F (F-R, the existing comparators): filled triangles;
      F picks are not joined: under F, x depends on the temperature, not only on S;
    - large marker: the best pick within budget B = 1 under each model (stage A + B), the ratios quoted in the text; the one-comparator
      SA marker uses A5.21's measurement of the same pick (seed 2028, 300,000 paired uses per point); the rule (2) marker at P1/P2
      is the same pick over 300,000 paired uses (P1: A5.19, seed 2028; P2: A5.15, seed 2027), x per K on those uses;
    - gray: A5's 128-sweep schedule compressed over S under E.
    Horizontal bars span K = 1..3 (x per K from flips.json, seed 1000 batch 50); vertical bars are paired 95 % CIs.
Data: a55/analysis.json (points.*.per_s, budget, picks.*.x.per_K); a5/a5.json, a5/a53.json (all in data/ber/);
data/results/a521/analysis.json; data/results/a519/analysis.json; data/results/a514/analysis_a515_a516_20261110.json.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as fs

fs.apply('price')
# Figure 1.83 in tall, x labels close to their ticks, (a,b) floor 0.0025; the page height is set here.
fs.PRINTED['price'] = (516.0, 511.547, 125.2)
FIG_H, BOT_PT, XLABEL_PAD, Y_FLOOR = 1.83, 27.3, 1.5, 0.0025
DATA = fs.DATA / 'ber' / 'a5'
RES = fs.DATA / 'results'
A5 = json.load(open(DATA / 'a5.json'))
A53 = json.load(open(DATA / 'a53.json'))
A55 = json.load(open(DATA.parent / 'a55' / 'analysis.json'))['points']
# one-comparator SA at B = 1, P1/P2: the same picks over 300,000 paired uses per point (A5.21); the cycles (x) are unchanged
A521 = json.load(open(RES / 'a521' / 'analysis.json'))['points']
# rule (2) first-accept at B = 1, P1/P2: the same picks over 300,000 paired uses per point (P1 A5.19 A16/C0, P2 A5.15 A32/C0);
# x is their held-out cycle factor per K on those uses
_A519 = json.load(open(RES / 'a519' / 'analysis.json'))
_A515 = json.load(open(RES / 'a514' / 'analysis_a515_a516_20261110.json'))['A515']
assert not _A519['P1']['A16_C0']['partial'] and _A515['A32_C0']['uses'] == 300000


def _x3(per_K):
    v = [per_K[k] for k in sorted(per_K)]
    return min(v), sum(v) / len(v), max(v)


FR1 = {'P1': dict(method=_A519['select']['held1']['A16'], x3=_x3(_A519['P1']['x']['A16']['x_per_K']),
                  **{k: _A519['P1']['A16_C0'][k] for k in ('ratio', 'lo', 'hi')}),
       'P2': dict(method=_A515['methods']['A32'], x3=_x3(_A515['x']['A32']['per_K']),
                  **{k: _A515['A32_C0'][k] for k in ('ratio', 'lo', 'hi')})}
SWEEPS = ['1', '2', '4', '8', '16', '32', '64', '128']
PT_COL, SA_COL, CHORD_COL, OLD_COL = fs.COMP_BLUE, fs.COMP_ORANGE, fs.OURS, fs.BASE2
# First-accept SA has its own colour; parallel trial is navy like one-comparator SA. The recolour maps
# OURS -> #8C1515 and COMP_BLUE -> #1966FF, and the Chord marker is Chord's colour.
ARPEGGIO_COL, STAR_COL = fs.COMP_BLUE, fs.OURS
PT_COL = fs.COMP_ORANGE
# S-label offsets (x factor, y factor, ha, va) where the default (below the point) would collide
# P1 '4' sits up-right of its enlarged marker, away from the S = 3 point
SLAB = {('P1', '1'): (1 / 1.18, 1.0, 'right', 'center'), ('P1', '4'): (1.22, 1.2, 'left', 'bottom'),
        ('P1', '16'): (1.0, 1.42, 'center', 'bottom'), ('P2', '1'): (1.0, 1.28, 'center', 'bottom'),
        ('P2', '4'): (1 / 1.03, 1.16, 'center', 'bottom')}   # above its circle, clear of the first-accept triangle
C1X = float(np.exp(np.mean(np.log([1 / 2, 1 / 4, 1 / 6]))))   # c = 1 at P = 2, 4, 6


def geo(v):
    return float(np.exp(np.mean(np.log(v))))


def cycle_span(shape, pick, S):
    r = [A53['cycles'][f'{shape}/{pick}/{S}'][k]['ratio'] for k in ('1', '2', '3')]
    return min(r), float(np.mean(r)), max(r)   # arithmetic mean over K, as the A5.5 budgets and SA markers


def pt_span(shape, budget):
    """Parallel trial modelled cycles relative to Chord, per K: I * (1 + ceil(log2 N)) / (L + F)."""
    out = []
    for K in (1, 2, 3):
        b = A5['a5d']['budgets'][f'{shape}_K{K}']
        I = b['I_equal_cycles'] if budget == 'cycles' else b['I_equal_flips']
        out.append(I * (1 + math.ceil(math.log2(b['N']))) / b['chord_cycles'])
    return min(out), float(np.mean(out)), max(out)   # arithmetic mean over K


NEAR = []   # markers drawn near (1, 1), redrawn above the Chord marker


def errpt(ax, x3, rec, color, marker, ms=3.4, zorder=3, mfc=None):
    lo, x, hi = x3
    y = rec['ratio']
    if abs(math.log10(x)) < 0.10 and abs(math.log10(y)) < 0.18:   # inside the Chord marker's extent on (a, b)'s log axes
        NEAR.append((ax, x, y, color, marker, ms, mfc))
    ylo, yhi = rec['ratio_ci']
    ax.errorbar([x], [y], xerr=[[x - lo], [hi - x]], yerr=[[y - ylo], [yhi - y]], fmt=marker, color=color, ms=ms,
                mfc=mfc if mfc else color, mec=color, ecolor=fs.ebar(color), elinewidth=fs.EBAR_LW, capsize=0, lw=0.8,
                zorder=zorder)


def a55_x3(point, method, model):
    """x per K under model 'E' or 'F' for a held-out A5.5 pick; the marker sits at the arithmetic mean over K (a55_plan.x_of)."""
    x = A55[point]['picks'][method]['x']
    v = [x['per_K'][k][f'x_{model}'] for k in sorted(x['per_K'])]
    return min(v), x['mean'][f'x_{model}'], max(v)


def a55_rec(r):
    return dict(ratio=r['ratio'], ratio_ci=[max(r['lo'], 0.0105), r['hi']])


def frontier(ax, point, shape, pick, old_series, title):
    # gray reference: A5's 128-sweep schedule compressed over S, cost E
    xs, ys = [], []
    for S in SWEEPS:
        rec = old_series(S)
        x3 = cycle_span(shape, pick, S)
        errpt(ax, x3, rec, OLD_COL, 'o', ms=2.2, zorder=2)
        xs.append(x3[1]); ys.append(rec['ratio'])
    ax.plot(xs, ys, color=OLD_COL, lw=0.7, zorder=1.5)
    ps = A55[point]['per_s']
    # SA re-tuned per S: E (filled circles, solid), F-M (open triangles, dotted), F-R (filled triangles)
    for arm, model, mk, ls, mfc, lab in (('fam', 'E', 'o', '-', None, True), ('fam', 'F', '^', (0, (1, 1.2)), 'white', False),
                                         ('far', 'F', '^', (0, (3, 1.5)), None, False)):
        col = SA_COL if model == 'E' else ARPEGGIO_COL
        xs, ys = [], []
        for S in [s for s in ('1', '2', '3', '4', '8', '16', '32', '64', '128') if f'{arm}/{s}' in ps]:
            r = ps[f'{arm}/{S}']
            x3 = a55_x3(point, r['method'], model)
            errpt(ax, x3, a55_rec(r), col, mk, ms=2.6, mfc=mfc)
            xs.append(x3[1]); ys.append(r['ratio'])
            if lab and S in ('1', '4', '16', '64', '128'):
                # S labels name the one-comparator (dark) points, in their colour, clear of the gray series
                dx, dy, ha, va = SLAB.get((point, S), (1.0, 1 / 1.32, 'center', 'top'))
                ax.text(x3[1] * dx, r['ratio'] * dy, S, fontsize=fs.ANNOT, color=SA_COL, ha=ha, va=va)
        if ls == '-':                 # E is a series in S; under F, x depends on T, so the picks are not joined
            ax.plot(xs, ys, color=SA_COL, lw=0.7, zorder=2)
    # Enlarge the best pick within B = 1 under each model.
    b = A55[point]['budget']
    for key, model in (('E/1', 'E'), ('F-R/1', 'F'), ('F-M/1', 'F')):
        r = b[key]
        if key == 'E/1':
            n = A521[point]
            assert n['SA'] == r['method'] and not n['partial'], (point, n['SA'], r['method'])
            r = dict(method=r['method'], ratio=n['ratio'], lo=n['lo'], hi=n['hi'])
        x3 = a55_x3(point, r['method'], model)
        if key == 'F-R/1' and point in FR1:
            n = FR1[point]
            assert n['method'] == r['method'], (point, n['method'], r['method'])
            r, x3 = dict(method=r['method'], ratio=n['ratio'], lo=n['lo'], hi=n['hi']), n['x3']
        mk = {'E/1': 'o', 'F-R/1': '^', 'F-M/1': '^'}[key]
        col = SA_COL if model == 'E' else ARPEGGIO_COL
        errpt(ax, x3, a55_rec(r), col, mk, ms=5.0, mfc='white' if key == 'F-M/1' else None, zorder=6.5)
    d = A5['a5d'][point]
    errpt(ax, pt_span(shape, 'cycles'), d['parallel trial, equal modelled cycles, P1-tuned'], PT_COL, 's',
          ms=3.0)
    errpt(ax, pt_span(shape, 'flips'), d['parallel trial, equal flips, P1-tuned'], PT_COL, 's', ms=3.0, mfc='white')
    ax.plot([1], [1], marker='+', color=STAR_COL, ms=6.0, mec=STAR_COL, mew=1.0, zorder=5, ls='none')
    for a, x, y, c, mk, ms, mfc in [n for n in NEAR if n[0] is ax]:
        # drawn again above the Chord marker with a surface rim, so a point near (1, 1) stays visible (as in (c))
        a.plot([x], [y], marker=mk, color=fs.SURF, ms=ms + 1.4, mec=fs.SURF, zorder=5.9, ls='none')   # surface halo
        a.plot([x], [y], marker=mk, color=c, ms=ms, mfc=mfc if mfc else c, mec=c, zorder=6, ls='none')
    ax.axhline(1, **fs.REF)
    ax.axvline(1, **fs.REF)
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlim(0.06, 100)
    ax.set_xticks([0.1, 0.3, 1, 3, 10, 30, 100]); ax.set_xticklabels(['0.1', '0.3', '1', '3', '10', '30', '100'])
    ax.set_yticks([0.02, 0.05, 0.2, 0.5, 1, 2, 5, 20]); ax.set_yticklabels(['0.02', '0.05', '0.2', '0.5', '1', '2', '5', '20'])
    ax.minorticks_off()
    ax.set_xlabel('Modeled cycles per anneal, relative to Chord', labelpad=XLABEL_PAD)
    fs.panel_title(ax, title[0], title[1])


def main():
    fig, axs = plt.subplots(1, 3, figsize=(fs.TEXT_W, FIG_H), gridspec_kw=dict(wspace=0.32, left=0.067, right=0.995,
                                                                             top=1 - 0.23 / FIG_H, bottom=BOT_PT / 72 / FIG_H))
    p1 = A53['sweeps_P1']['series']
    frontier(axs[0], 'P1', 'x16', 'old', lambda S: p1[S]['old'], ('a', '16 users, 16-QAM, 20 dB, $N_\\mathrm{s}=32$'))
    p2 = A5['a5a']['sweeps_P2']
    frontier(axs[1], 'P2', 'x32', 'sa2', lambda S: p2[S], ('b', '32 users, 16-QAM, 22 dB, $N_\\mathrm{s}=8$'))
    for ax in axs[:2]:
        ax.set_ylim(Y_FLOOR, 40)   # the floor keeps the (a) legend under every error bar
    axs[0].set_ylabel('BER relative to Chord')
    key = [Line2D([], [], color=SA_COL, lw=0.7, marker='o', ms=2.6, label='SA, one comparator'),
           Line2D([], [], color=ARPEGGIO_COL, ls='none', marker='^', ms=2.6, label='Arpeggio, rule (2)'),
           Line2D([], [], color=ARPEGGIO_COL, ls='none', marker='^', ms=2.6, mfc='white',
                  label='Arpeggio, Metropolis'),
           Line2D([], [], color=fs.INK, ls='none', marker='o', ms=5.0, mfc=fs.INK, label='Large: $B=1$ pick'),
           Line2D([], [], color=OLD_COL, lw=0.7, marker='o', ms=2.2, label='SA, 128-sweep schedule compressed')]
    # opaque legend boxes between the dotted guides (zorder 0.6) and the data (zorder >= 2), and a y floor so the
    # (a) legend sits below every error bar: no guide or error bar crosses legend text
    LEG = dict(frameon=True, facecolor=fs.SURF, edgecolor='none', framealpha=1.0)
    axs[0].legend(handles=key, loc='lower right', handlelength=1.6, handletextpad=0.4,
                  labelspacing=0.22, borderaxespad=0.15, borderpad=0.2, **LEG).set_zorder(1.6)
    key2 = [Line2D([], [], color=PT_COL, ls='none', marker='s', ms=3.0, label='parallel trial, equal cycles'),
            Line2D([], [], color=PT_COL, ls='none', marker='s', ms=3.0, mfc='white', label='parallel trial, equal flips'),
            Line2D([], [], color=STAR_COL, ls='none', marker='+', ms=6.0, mec=STAR_COL, mew=1.0, label='Chord')]
    axs[1].legend(handles=key2, loc='lower left', handlelength=1.2, handletextpad=0.4,
                  labelspacing=0.22, borderaxespad=0.15, borderpad=0.2, **LEG).set_zorder(1.6)

    # (c) colour sweep
    ax = axs[2]
    cols = {'P1': (fs.BASE1, 'o', '16 users', '-'), 'P2': (fs.BASE2, 'D', '32 users', (0, (3, 1.5)))}
    handles = []
    for point, (col, mk, lab, ls) in cols.items():
        curve = A5['a5b'][point]['curve']
        xs, ys = [], []
        for k, rec in curve.items():
            m = rec['m']
            x3 = (1 / 6, C1X, 1 / 2) if m == 0 else (m, m, m)
            if m == 1:
                errpt(ax, x3, rec, CHORD_COL, mk, ms=3.2, zorder=4)
                # drawn again above the Chord marker with a surface rim, so the 16-user point near (1, 1) stays visible
                ax.plot([x3[1]], [rec['ratio']], marker=mk, color=CHORD_COL, ms=3.2, mec=fs.SURF, mew=0.5, zorder=6, ls='none')
            else:
                errpt(ax, x3, rec, col, mk, ms=2.8)
            xs.append(x3[1]); ys.append(rec['ratio'])
        ax.plot(xs, ys, color=col, lw=0.8, ls=ls, zorder=2)
        handles.append(Line2D([], [], color=col, lw=0.8, ls=ls, marker=mk, ms=2.8, label=lab))
        b1 = A5['a5b'][point]['controls']['b1 dimension colours, copies in phase (tuned)']
        errpt(ax, (1.0, 1.0, 1.0), b1, col, mk, ms=3.0, mfc='white')
    # Use the same Chord marker in all panels. The P-colors points also use Chord's colour.
    ax.plot([1], [1], marker='+', color=STAR_COL, ms=6.0, mec=STAR_COL, mew=1.0, zorder=5, ls='none')
    ax.axhline(1, **fs.REF)
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlim(0.13, 50); ax.set_ylim(0.15, 40)
    ax.set_yticks([0.2, 0.5, 1, 2, 5, 10, 20]); ax.set_yticklabels(['0.2', '0.5', '1', '2', '5', '10', '20'])
    ax.set_xticks([C1X, 1, 2, 4, 8, 16, 32])
    ax.set_xticklabels(['1', '$P$', '2$P$', '4$P$', '8$P$', '16$P$', '32$P$'])
    ax.minorticks_off()
    # decision steps per sweep (model (4) also charges flips)
    ax.set_xlabel('Colors (decision steps per sweep)', labelpad=XLABEL_PAD)
    ax.legend(handles=handles, loc='upper right', handlelength=1.4, borderaxespad=0.2)
    ax.text(1.22, 3.2, 'lockstep copies,\nactivity $1/P$ (open)', fontsize=fs.ANNOT, color=fs.INK, ha='left',
            va='bottom')
    ax.text(0.145, 23, '$1/P$, $P=2$–$6$', fontsize=fs.ANNOT, color=fs.BASE1, ha='left', va='bottom')
    # each N/2 label beside its own series' point: 16 users at 16P (circle), 32 users at 32P (diamond)
    ax.text(16 * 1.13, 0.682, '$N/2$', fontsize=fs.ANNOT, color=fs.BASE1, ha='left', va='center')
    ax.text(32, 0.36, '$N/2$', fontsize=fs.ANNOT, color=fs.BASE2, ha='center', va='top')
    ax.set_ylabel('BER relative to Chord')   # (c) names its own axis
    fs.panel_title(ax, 'c', 'Color count, re-tuned on one grid')
    for a in axs:
        a.xaxis.set_label_coords(0.5, -0.155)
    out = fs.OUT
    out.mkdir(exist_ok=True)
    meta = {'Author': '', 'Creator': '', 'Producer': '', 'Title': 'price', 'CreationDate': None, 'ModDate': None}
    fig.savefig(out / 'price.pdf', metadata=meta, dpi=600,
                bbox_inches=fs._fixed_bbox(fig, 'price') if 'price' in fs.PRINTED else 'tight')
    fig.savefig(out / 'price.png', dpi=200, bbox_inches='tight')
    print('wrote', out / 'price.pdf')


if __name__ == '__main__':
    main()
