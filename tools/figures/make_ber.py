"""Fig. 4: BER against SNR inside the MDI wrapper, 16x16 and 32x32 16-QAM (held-out seed 101).

Includes the held-out width-128 sweep, with bootstrap CIs recomputed from saved per-use error counts.
Points are the Table III runs (>= 100 erroneous uses and >= 100 bit errors per point, capped at 1e7 bits); vertical
bars are 95 % cluster-bootstrap CIs; zero-error points are not drawn.
Data: table2/table2_curves.csv.
"""
import csv
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt

import figstyle as fs

fs.apply('ber')
# Figure 1.78 in tall, a 44 pt bottom margin and the x label close to its ticks; the page height is set here.
fs.PRINTED['ber'] = (252.0, 256.29, 124.6)
FIG_H, TOP_PT, BOT_PT, XLABEL_PAD = 1.78, 14.0, 44.0, 1.5
DATA = fs.ROOT.parent / 'work' / 'plan_20261024' / 'arpeggio_ber' / 'data' / 'table2' / 'table2_curves.csv'

SERIES = [  # (row in table2_curves.csv, label, colour, linestyle, marker, line width)
    # baselines gray (told apart by marker and dash), the published MDI-AHC solver purple, Chord green
    ('MMSE-SIC', 'MMSE-SIC', fs.BASE2, '-', 'v', 0.8),
    ('K-best, 32 candidates', 'K-best, 32', fs.BASE1, '-', 's', 0.8),
    ('K-best, 128 candidates', 'K-best, 128', fs.BASE1, '--', 's', 0.9),
    ('ML (sphere decoder)', 'SD proxy', fs.INK, ':', None, 0.8),
    ('MDI-AHC (b)', 'MDI-AHC', fs.COMP_PURPLE, '-', '^', 0.8),
    ('Chord (b)', 'Chord', fs.OURS, '-', 'o', 1.1),
    ('MDI-AHC, Ns = 8', 'MDI-AHC, $N_\\mathrm{s}=8$', fs.COMP_PURPLE, (0, (2, 1.5)), None, 0.8),   # short dashes vs Chord's long dashes
    ('Chord, Ns = 8', 'Chord, $N_\\mathrm{s}=8$', fs.OURS, '--', None, 1.1),
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
        ax.set_xlabel('SNR (dB)', labelpad=XLABEL_PAD)   # close to the ticks, so the figure keeps a gap above the legend
        fs.panel_title(ax, *title)
    axs[0].set_ylabel('Bit error rate')
    # Legend ours first, in a 4 x 2 grid filled by column: each solid line sits above its N_s = 8 variant.
    h, l = axs[0].get_legend_handles_labels()
    order = ['Chord', 'Chord, $N_\\mathrm{s}=8$', 'MDI-AHC', 'MDI-AHC, $N_\\mathrm{s}=8$', 'K-best, 32', 'K-best, 128',
             'MMSE-SIC', 'SD proxy']
    hl = dict(zip(l, h))     # key: line + marker only (h[...][0]), no CI stroke
    fig.legend([hl[k][0] for k in order], order, loc='lower center', ncol=4, handlelength=1.5, handletextpad=0.4,
               columnspacing=0.8, labelspacing=0.3, bbox_to_anchor=(0.52, -0.01))
    fs.save(fig, 'Chord', 'ber')


if __name__ == '__main__':
    main()
