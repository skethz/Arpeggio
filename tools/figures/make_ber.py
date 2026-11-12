"""Labels since 9 Nov 2026 (user "Apply it"): Chord (was Antiphase), Arpeggio (first-accept); work/rename_chord_arpeggio_20261109/.
Fig. 3 of the Antiphase paper: BER against SNR inside the MDI wrapper, 16x16 and 32x32 16-QAM (held-out seed 101).

Includes the completed held-out width-128 sweep, with bootstrap CIs recomputed from saved per-use error counts.
Points are the Table II rerun (>= 100 erroneous uses and >= 100 bit errors per point, capped at 1e7 bits); vertical
bars are 95 % cluster-bootstrap CIs; zero-error points are not drawn.
Data: work/plan_20261024/ap_ber/data/table2/table2_curves.csv (ap_ber RESULTS.md section 1). Built from the data only.
"""
import csv
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt

import figstyle as fs

fs.apply('ber')
# Round-8 fit (8 Nov 2026): figure 1.78 in tall (was 1.95) with the same top margin, a 44 pt bottom margin (was 50.5) and
# the x label closer to its ticks; the page height is set here, the shared figstyle.PRINTED['ber'] (137.056 pt) stays.
fs.PRINTED['ber'] = (252.0, 256.29, 124.6)
FIG_H, TOP_PT, BOT_PT, XLABEL_PAD = 1.78, 14.0, 44.0, 1.5
DATA = fs.ROOT.parent / 'work' / 'plan_20261024' / 'ap_ber' / 'data' / 'table2' / 'table2_curves.csv'

SERIES = [  # (row in table2_curves.csv, label, colour, linestyle, marker, line width)
    # baselines gray (told apart by marker and dash), the published MDI-AHC solver purple, Antiphase green
    ('MMSE-SIC', 'MMSE-SIC', fs.BASE2, '-', 'v', 0.8),
    ('K-best, 32 candidates', 'K-best, 32', fs.BASE1, '-', 's', 0.8),
    ('K-best, 128 candidates', 'K-best, 128', fs.BASE1, '--', 's', 0.9),
    ('ML (sphere decoder)', 'SD proxy', fs.INK, ':', None, 0.8),
    ('MDI-AHC (b)', 'MDI-AHC', fs.COMP_PURPLE, '-', '^', 0.8),
    ('Antiphase (b)', 'Chord', fs.OURS, '-', 'o', 1.1),
    ('MDI-AHC, Ns = 8', 'MDI-AHC, $N_\\mathrm{s}=8$', fs.COMP_PURPLE, (0, (2, 1.5)), None, 0.8),   # short dashes vs Antiphase's long dashes
    ('Antiphase, Ns = 8', 'Chord, $N_\\mathrm{s}=8$', fs.OURS, '--', None, 1.1),
]


def load():
    d = defaultdict(list)
    with open(DATA) as f:
        for r in csv.DictReader(f):
            d[(r['shape'], r['row'])].append((float(r['snr_dB']), float(r['ber']), float(r['boot95_lo']),
                                              float(r['boot95_hi'])))
    with open(fs.WORK.parent / 'data' / 'kbest128_curves.csv') as f:
        for r in csv.DictReader(f):
            d[(r['shape'], r['row'])].append(tuple(float(r[k]) for k in ('snr_dB', 'ber', 'boot95_lo', 'boot95_hi')))
    return {k: np.array(sorted(v)) for k, v in d.items()}


def main():
    curves = load()
    fig, axs = plt.subplots(1, 2, figsize=(fs.COL_W, FIG_H), sharey=True,
                            gridspec_kw=dict(wspace=0.08, left=0.14, right=0.99, top=1 - TOP_PT / 72 / FIG_H,
                                             bottom=BOT_PT / 72 / FIG_H))
    for ax, shape, title, xlim in ((axs[0], 'x16', ('a', '16 users, 16-QAM'), (16.5, 28.5)),
                                   (axs[1], 'x32', ('b', '32 users, 16-QAM'), (16.5, 28.5))):
        for row, label, col, ls, mk, lw in SERIES:
            a = curves.get((shape, row))
            if a is None:
                continue
            a = a[(a[:, 1] > 0) & (a[:, 0] <= xlim[1])]
            # CI bars: thin, capless, the series colour at reduced opacity, clipped at the 1e-6 floor of the axes
            ax.errorbar(a[:, 0], a[:, 1], yerr=[a[:, 1] - a[:, 2], a[:, 3] - a[:, 1]], color=col, ls=ls, lw=lw,
                        marker=mk, ms=1.7, mfc=fs.SURF if row == 'K-best, 128 candidates' else col, ecolor=fs.ebar(col), elinewidth=fs.EBAR_LW, capsize=0, label=label)
        for y in (1e-3, 1e-4):
            ax.axhline(y, **fs.REF)
        ax.set_yscale('log')
        ax.set_xlim(*xlim)
        ax.set_ylim(1e-6, 3e-2)
        ax.set_xlabel('SNR (dB)', labelpad=XLABEL_PAD)   # closer to the ticks, so the shorter figure keeps a gap above the legend
        fs.panel_title(ax, *title)
    axs[0].set_ylabel('Bit error rate')
    # Legend ours first, in a 4 x 2 grid filled by column: each solid line sits above its N_s = 8 variant.
    h, l = axs[0].get_legend_handles_labels()
    order = ['Chord', 'Chord, $N_\\mathrm{s}=8$', 'MDI-AHC', 'MDI-AHC, $N_\\mathrm{s}=8$', 'K-best, 32', 'K-best, 128',
             'MMSE-SIC', 'SD proxy']
    hl = dict(zip(l, h))     # key: line + marker only (h[...][0]), no CI stroke
    fig.legend([hl[k][0] for k in order], order, loc='lower center', ncol=4, handlelength=1.5, handletextpad=0.4,
               columnspacing=0.8, labelspacing=0.3, bbox_to_anchor=(0.52, -0.01))
    fs.save(fig, 'Antiphase', 'ber')


if __name__ == '__main__':
    main()
