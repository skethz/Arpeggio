"""Labels since 9 Nov 2026 (user "Apply it"): Chord (was Antiphase), Arpeggio (first-accept); work/rename_chord_arpeggio_20261109/.
PREVIEW copy (A5.5 row-2 wording, 6 Nov 2026): Fig. 3(a,b) with A5.5's SA re-tuned per sweep count (PROTOCOL_A55 sec. 9:
new SA series under E and under F, F-R and F-M marked apart, the compressed series as a gray reference). Writes raw/ here
only; the project figure is untouched. Panel (c) and the parallel-trial points are as in the project figure.

(a), (b) BER relative to Antiphase (i) against modeled cycles per anneal relative to Antiphase, held-out seed 102:
    - SA re-tuned per S (per-S picks, stage A on seed 1000), cost E = S N + F_SA (Eq. (4)): filled circles, solid;
    - the same Metropolis picks under first-accept cost F = tests + F_SA (F-M, a Metropolis unit per lane): open triangles;
    - rule (2) first-accept per-S picks under F (F-R, the existing comparators): filled diamonds;
      F picks are not joined: under F, x depends on the temperature, not only on S;
    - ring: the best pick within budget B = 1 under each model (stage A + B), the ratios quoted in the text;
    - gray: A5's 128-sweep schedule compressed over S under E (the earlier series).
    Horizontal bars span K = 1..3 (x per K from flips.json, seed 1000 batch 50); vertical bars are paired 95 % CIs.
Data: ap_ber/data/a55/analysis.json (points.*.per_s, budget, picks.*.x.per_K); a5/a5.json, a5/a53.json as before.
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
# Round-8 fit (8 Nov 2026): figure 1.83 in tall (was 2.0), x labels closer to their ticks, (a,b) floor 0.0025; the page
# height is set here, the shared figstyle.PRINTED['price'] (137.24 pt) stays as it is.
fs.PRINTED['price'] = (516.0, 511.547, 125.2)
FIG_H, BOT_PT, XLABEL_PAD, Y_FLOOR = 1.83, 27.3, 1.5, 0.0025
DATA = fs.ROOT / 'work' / 'plan_20261024' / 'ap_ber' / 'data' / 'a5'
A5 = json.load(open(DATA / 'a5.json'))
A53 = json.load(open(DATA / 'a53.json'))
A55 = json.load(open(DATA.parent / 'a55' / 'analysis.json'))['points']
SWEEPS = ['1', '2', '4', '8', '16', '32', '64', '128']
PT_COL, SA_COL, AP_COL, OLD_COL = fs.COMP_BLUE, fs.COMP_ORANGE, fs.OURS, fs.BASE2
# Sequential reframe highlight (user: "Apply all three", 9 Nov 2026): first-accept SA, the headline's winner, has its own colour;
# parallel trial trails, navy like one-comparator SA. Since the user's palette of 9 Nov 2026 (Antiphase #8C1515, first-accept #1966FF)
# the recolour maps OURS -> #8C1515 and COMP_BLUE -> #1966FF, and the Antiphase star is Antiphase's colour again.
FA_COL, STAR_COL = fs.COMP_BLUE, fs.OURS
PT_COL = fs.COMP_ORANGE
# S-label offsets (x factor, y factor, ha, va) where the default (below the point) would collide
# P1 '4' sits up-right of its ringed point, away from the S = 3 point it read as (round-8 audit 5.2, 8 Nov 2026)
SLAB = {('P1', '1'): (1 / 1.18, 1.0, 'right', 'center'), ('P1', '4'): (1.22, 1.2, 'left', 'bottom'),
        ('P1', '16'): (1.0, 1.42, 'center', 'bottom'), ('P2', '1'): (1.0, 1.28, 'center', 'bottom'),
        ('P2', '4'): (1 / 1.03, 1.16, 'center', 'bottom')}   # above its circle, clear of the first-accept diamond (round-6 review 19, 8 Nov 2026)
C1X = float(np.exp(np.mean(np.log([1 / 2, 1 / 4, 1 / 6]))))   # c = 1 at P = 2, 4, 6


def geo(v):
    return float(np.exp(np.mean(np.log(v))))


def cycle_span(shape, pick, S):
    r = [A53['cycles'][f'{shape}/{pick}/{S}'][k]['ratio'] for k in ('1', '2', '3')]
    return min(r), float(np.mean(r)), max(r)   # arithmetic mean over K, as the A5.5 budgets and SA markers (round 3, 8 Nov 2026)


def pt_span(shape, budget):
    """Parallel trial modelled cycles relative to Antiphase, per K: I * (1 + ceil(log2 N)) / (L + F)."""
    out = []
    for K in (1, 2, 3):
        b = A5['a5d']['budgets'][f'{shape}_K{K}']
        I = b['I_equal_cycles'] if budget == 'cycles' else b['I_equal_flips']
        out.append(I * (1 + math.ceil(math.log2(b['N']))) / b['antiphase_cycles'])
    return min(out), float(np.mean(out)), max(out)   # arithmetic mean over K (round 3, 8 Nov 2026)


NEAR = []   # markers drawn near (1, 1), redrawn above the Antiphase star (round-6 review 19, 8 Nov 2026)


def errpt(ax, x3, rec, color, marker, ms=3.4, zorder=3, mfc=None):
    lo, x, hi = x3
    y = rec['ratio']
    if abs(math.log10(x)) < 0.10 and abs(math.log10(y)) < 0.18:   # inside the star's extent on (a, b)'s log axes
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
    # gray reference: A5's 128-sweep schedule compressed over S (the earlier Fig. 3 series), cost E
    xs, ys = [], []
    for S in SWEEPS:
        rec = old_series(S)
        x3 = cycle_span(shape, pick, S)
        errpt(ax, x3, rec, OLD_COL, 'o', ms=2.2, zorder=2)
        xs.append(x3[1]); ys.append(rec['ratio'])
    ax.plot(xs, ys, color=OLD_COL, lw=0.7, zorder=1.5)
    ps = A55[point]['per_s']
    # SA re-tuned per S: E (filled circles, solid), F-M (open triangles, dotted), F-R (diamonds, dashed)
    for arm, model, mk, ls, mfc, lab in (('fam', 'E', 'o', '-', None, True), ('fam', 'F', '^', (0, (1, 1.2)), 'white', False),
                                         ('far', 'F', 'D', (0, (3, 1.5)), None, False)):
        col = SA_COL if model == 'E' else FA_COL
        xs, ys = [], []
        for S in [s for s in ('1', '2', '3', '4', '8', '16', '32', '64', '128') if f'{arm}/{s}' in ps]:
            r = ps[f'{arm}/{S}']
            x3 = a55_x3(point, r['method'], model)
            errpt(ax, x3, a55_rec(r), col, mk, ms=2.6 if mk != 'D' else 2.3, mfc=mfc)
            xs.append(x3[1]); ys.append(r['ratio'])
            if lab and S in ('1', '4', '16', '64', '128'):
                # S labels name the one-comparator (dark) points, in their colour, clear of the gray series (round-2 audit 5.7, 8 Nov 2026)
                dx, dy, ha, va = SLAB.get((point, S), (1.0, 1 / 1.32, 'center', 'top'))
                ax.text(x3[1] * dx, r['ratio'] * dy, S, fontsize=fs.ANNOT, color=SA_COL, ha=ha, va=va)
        if ls == '-':                 # E is a series in S; under F, x depends on T, so the picks are not joined
            ax.plot(xs, ys, color=SA_COL, lw=0.7, zorder=2)
    # rings: best pick within B = 1 under each model (the ratios quoted in the text)
    b = A55[point]['budget']
    for key, model in (('E/1', 'E'), ('F-R/1', 'F'), ('F-M/1', 'F')):
        r = b[key]
        x3 = a55_x3(point, r['method'], model)
        mk = {'E/1': 'o', 'F-R/1': 'D', 'F-M/1': '^'}[key]
        col = SA_COL if model == 'E' else FA_COL
        errpt(ax, x3, a55_rec(r), col, mk, ms=2.6, mfc='white' if key == 'F-M/1' else None, zorder=4)
        # rings above the surface halos of points redrawn near (1, 1), so no ring looks broken (round-8 review R8.12, 8 Nov 2026)
        ax.plot([x3[1]], [r['ratio']], marker='o', ms=6.4, mfc='none', mec=col, mew=0.6, ls='none', zorder=6.5)
    d = A5['a5d'][point]
    errpt(ax, pt_span(shape, 'cycles'), d['parallel trial, equal modelled cycles, P1-tuned (kill arm)'], PT_COL, 's',
          ms=3.0)
    errpt(ax, pt_span(shape, 'flips'), d['parallel trial, equal flips, P1-tuned'], PT_COL, 's', ms=3.0, mfc='white')
    ax.plot([1], [1], marker='*', color=STAR_COL, ms=8.5, mec=fs.SURF, mew=0.4, zorder=5, ls='none')
    for a, x, y, c, mk, ms, mfc in [n for n in NEAR if n[0] is ax]:
        # drawn again above the star with a surface rim, so a point near (1, 1) stays visible (as in (c), round 4)
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
        ax.set_ylim(Y_FLOOR, 40)   # was 0.01, then 0.004; lower floor keeps the (a) legend under every error bar (round-5 audit 5.4; round 8)
    axs[0].set_ylabel('BER relative to Chord')
    # 'SA, one comparator': '(E)' was A5.5's internal arm label (blind review, 8 Nov 2026). Comment moved off the
    # code line on 8 Nov 2026 (round 1): inline, it swallowed the closing '),' and the script did not parse.
    key = [Line2D([], [], color=SA_COL, lw=0.7, marker='o', ms=2.6, label='SA, one comparator'),
           Line2D([], [], color=FA_COL, ls='none', marker='D', ms=2.3, label='Arpeggio, rule (2)'),
           Line2D([], [], color=FA_COL, ls='none', marker='^', ms=2.6, mfc='white',
                  label='Arpeggio, Metropolis'),
           Line2D([], [], color=fs.INK, ls='none', marker='o', ms=6.4, mfc='none', mew=0.6, label='$B=1$ pick'),
           Line2D([], [], color=OLD_COL, lw=0.7, marker='o', ms=2.2, label='SA, 128-sweep schedule compressed')]
    # opaque legend boxes between the dotted guides (zorder 0.6) and the data (zorder >= 2), and a lower y floor so the
    # (a) legend sits below every error bar: no guide or error bar crosses legend text (round-5 audit 5.4, 8 Nov 2026)
    LEG = dict(frameon=True, facecolor=fs.SURF, edgecolor='none', framealpha=1.0)
    axs[0].legend(handles=key, loc='lower right', handlelength=1.6, handletextpad=0.4,
                  labelspacing=0.22, borderaxespad=0.15, borderpad=0.2, **LEG).set_zorder(1.6)
    key2 = [Line2D([], [], color=PT_COL, ls='none', marker='s', ms=3.0, label='parallel trial, equal cycles'),
            Line2D([], [], color=PT_COL, ls='none', marker='s', ms=3.0, mfc='white', label='parallel trial, equal flips'),
            Line2D([], [], color=STAR_COL, ls='none', marker='*', ms=6.5, mec=fs.SURF, mew=0.4, label='Chord')]
    axs[1].legend(handles=key2, loc='lower left', handlelength=1.2, handletextpad=0.4,
                  labelspacing=0.22, borderaxespad=0.15, borderpad=0.2, **LEG).set_zorder(1.6)

    # (c) colour sweep, unchanged from the project figure
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
                errpt(ax, x3, rec, AP_COL, mk, ms=3.2, zorder=4)
                # drawn again above the Antiphase star with a surface rim, so the 16-user point near (1, 1) stays visible (round 4, 8 Nov 2026)
                ax.plot([x3[1]], [rec['ratio']], marker=mk, color=AP_COL, ms=3.2, mec=fs.SURF, mew=0.5, zorder=6, ls='none')
            else:
                errpt(ax, x3, rec, col, mk, ms=2.8)
            xs.append(x3[1]); ys.append(rec['ratio'])
        ax.plot(xs, ys, color=col, lw=0.8, ls=ls, zorder=2)
        handles.append(Line2D([], [], color=col, lw=0.8, ls=ls, marker=mk, ms=2.8, label=lab))
        b1 = A5['a5b'][point]['controls']['b1 dimension colours, copies in phase (tuned)']
        errpt(ax, (1.0, 1.0, 1.0), b1, col, mk, ms=3.0, mfc='white')
    # (c) star in the same colour as (a, b) and the (b) legend; the P-colors points stay blue (caption: 'blue; star: Antiphase')
    ax.plot([1], [1], marker='*', color=STAR_COL, ms=8.5, mec=fs.SURF, mew=0.4, zorder=5, ls='none')
    ax.axhline(1, **fs.REF)
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlim(0.13, 50); ax.set_ylim(0.15, 40)
    ax.set_yticks([0.2, 0.5, 1, 2, 5, 10, 20]); ax.set_yticklabels(['0.2', '0.5', '1', '2', '5', '10', '20'])
    ax.set_xticks([C1X, 1, 2, 4, 8, 16, 32])
    ax.set_xticklabels(['1', '$P$', '2$P$', '4$P$', '8$P$', '16$P$', '32$P$'])
    ax.minorticks_off()
    # Decision steps per sweep, not 'dependent steps proportional to colors': model (4) also charges flips (round-7 review R7.9, 8 Nov 2026)
    ax.set_xlabel('Colors (decision steps per sweep)', labelpad=XLABEL_PAD)
    ax.legend(handles=handles, loc='upper right', handlelength=1.4, borderaxespad=0.2)
    # 'lockstep copies', not 'copies in phase', which reads as I/Q (blind review, 8 Nov 2026)
    ax.text(1.22, 3.2, 'lockstep copies,\nactivity $1/P$ (open)', fontsize=fs.ANNOT, color=fs.INK, ha='left',
            va='bottom')
    ax.text(0.145, 23, '$1/P$, $P=2$–$6$', fontsize=fs.ANNOT, color=fs.BASE1, ha='left', va='bottom')
    # each N/2 label beside its own series' point: 16 users at 16P (circle), 32 users at 32P (diamond) (round 5, 8 Nov 2026)
    ax.text(16 * 1.13, 0.682, '$N/2$', fontsize=fs.ANNOT, color=fs.BASE1, ha='left', va='center')
    ax.text(32, 0.36, '$N/2$', fontsize=fs.ANNOT, color=fs.BASE2, ha='center', va='top')
    ax.set_ylabel('BER relative to Chord')   # (c) names its own axis (round 5, 8 Nov 2026)
    fs.panel_title(ax, 'c', 'Color count, re-tuned on one grid')
    for a in axs:
        a.xaxis.set_label_coords(0.5, -0.155)
    out = Path(__file__).resolve().parent / 'raw'
    meta = {'Author': '', 'Creator': '', 'Producer': '', 'Title': 'price'}
    fig.savefig(out / 'price.pdf', metadata=meta, dpi=600,
                bbox_inches=fs._fixed_bbox(fig, 'price') if 'price' in fs.PRINTED else 'tight')
    fig.savefig(out / 'price.png', dpi=200, bbox_inches='tight')
    print('wrote', out / 'price.pdf')


if __name__ == '__main__':
    main()
