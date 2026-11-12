"""Antiphase: accepted flow-v2 rev4 GF22 layouts of the D=128, 64 and 32 engines at one common scale (column width).

Each engine shows its Innovus routed view (all routing layers; GUI text and violation overlays hidden) directly above
its placed cells colored by RTL function (server-side aggregate raster). Dies are rotated 90 degrees counterclockwise
so the long axis runs horizontally (memory-macro column at the bottom edge). One scale bar serves every panel.
Data: <PROJECT>/data/asic_layout_r4/ (see PROVENANCE.md there).
"""
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import figstyle as fs
import layoutlib as ll

fs.apply('asic_layout_r4')
P = fs.ROOT / 'Antiphase_DAC27' / 'data' / 'asic_layout_r4'
# Categorical RTL-function map: the supplied palette is all blues and grays, which merge on the map, so each logic
# function gets its own hue family. Blue is the palette's; orange, green and yellow are added for this figure only.
COLORS = {'Coupling and schedule memory': '#53565A', 'Multipliers (decision or MAC)': '#0077C8',
          'Adders and nonlinear units': '#E06A00', 'State and control registers': '#00A36A',
          'RNG and seeding': '#F2C200', 'Unattributed logic and buffers': '#CBCCCD'}
# Legend names follow the RTL-name rules (rules_ape.json): 'Multipliers' held the decision stages (d0-d2, dec_) with the
# per-lane temperature multiplies (MULT), and 'nonlinear units' held only synthesized carry-save adder trees (csa_tree)
# (round-3 review 15, audit 5.6, 8 Nov 2026). Group keys, colours and the map are unchanged.
LABELS = [('Memory macros', 'Coupling and schedule memory'), ('Decision stages', 'Multipliers (decision or MAC)'),
          ('Adder trees', 'Adders and nonlinear units'),
          ('State, control registers', 'State and control registers'),
          ('RNG, seeding', 'RNG and seeding'), ('Unattributed logic', 'Unattributed logic and buffers')]
CASES = [('ape_d128_p1200_r4', 'a', 128, '1.20'), ('ape_d64_r4', 'b', 64, '1.00'), ('ape_d32_p1150_r4', 'c', 32, '1.15')]


def load(name):
    cols, g = ll.group_colors(P / f'{name}_groups_public.json', COLORS)
    fmap, _ = ll.function_map(P / f'{name}_raster_public.npz', cols, max_px=1600)
    routed, _ = ll.routed_view(P / f'{name}_routed_public.png', g['die_um'], max_px=2600)
    # Both arrays to origin-upper, then rotate 90 deg counterclockwise (die top -> left, die left -> bottom).
    fmap = np.rot90(np.flipud(fmap))
    routed = np.rot90(routed)
    w_um, h_um = g['die_um']
    return dict(g=g, fmap=fmap, routed=routed, ext=[0, h_um, 0, w_um], L=h_um, T=w_um)


E = {name: load(name) for name, *_ in CASES}


def shown_colours(k=8, share=0.6, filled=0.3):
    """Legend swatch per group: the colour the map really shows. Occupancy shading and white gaps make the map paler than
    the group colour, so average the rendered map over the k-px blocks that the group dominates, counting the group's
    pixels and the white gaps but not other groups' pixels, which would tint the swatch."""
    acc = {n: [np.zeros(3), 0] for n in COLORS}
    for name, *_ in CASES:
        cols, g = ll.group_colors(P / f'{name}_groups_public.json', COLORS)
        dom = np.load(P / f'{name}_raster_public.npz')['dominant']
        rgb = ll.function_map(P / f'{name}_raster_public.npz', cols, max_px=1600)[0] / 255.0
        h, w = dom.shape[0] // k, dom.shape[1] // k
        bdom = dom[:h * k, :w * k].reshape(h, k, w, k).transpose(0, 2, 1, 3).reshape(h, w, -1)
        brgb = rgb[:h * k, :w * k].reshape(h, k, w, k, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, -1, 3)
        occupied = (bdom != 255).sum(-1)
        for gi, n in enumerate(g['groups']):
            m = ((bdom == gi).sum(-1) >= share * occupied) & (occupied >= filled * k * k)
            keep = (bdom[m] == gi) | (bdom[m] == 255)
            acc[n][0] += (brgb[m] * keep[..., None]).sum((0, 1))
            acc[n][1] += int(keep.sum())
    return {n: '#%02X%02X%02X' % tuple(int(round(x * 255)) for x in v / c) for n, (v, c) in acc.items()}


SHOWN = shown_colours()
print('legend swatches', SHOWN)
FW = fs.COL_W
m = 0.03                                   # side margin (in)
S = (FW - 2 * m) / E['ape_d128_p1200_r4']['L']   # inches per micrometre, shared by all panels
# top_pad + block_gap = 0.05 in as before (FH unchanged); top_pad makes room for the title baseline 4 pt above panel (a).
title_h, pair_gap, block_gap, col_gap, leg_h, top_pad = 0.15, 0.022, 0.03, 0.10, 0.27, 0.02
blk1 = title_h + 2 * E['ape_d128_p1200_r4']['T'] * S + pair_gap
t2 = max(E[n]['T'] for n in ('ape_d64_r4', 'ape_d32_p1150_r4')) * S
blk2 = title_h + 2 * t2 + pair_gap
FH = top_pad + blk1 + block_gap + blk2 + leg_h
fig = plt.figure(figsize=(FW, FH))


def add(x, y_top, name, kind):
    """Axes at (x, y_top) in inches from the top-left corner; size from the common scale."""
    e = E[name]
    w, h = e['L'] * S, e['T'] * S
    ax = fig.add_axes([x / FW, 1 - (y_top + h) / FH, w / FW, h / FH])
    ax.imshow(e['routed'] if kind == 'r' else e['fmap'], extent=e['ext'], origin='upper', interpolation='lanczos')
    ll.frame(ax, e['ext'])
    return ax, h


def title(x, y_top, text):
    """Panel title as in the plotted figures: left-aligned on the panel, baseline 4 pt above it, LABEL size."""
    fig.text(x / FW, 1 - (y_top + title_h - 4 / 72) / FH, text, ha='left', va='baseline', fontsize=fs.LABEL,
             color=fs.INK)


# Block 1: D=128.
y = top_pad
name, letter, D, clk = CASES[0]
title(m, y, f'({letter}) $D$={D}, {clk} ns')
_, h = add(m, y + title_h, name, 'r')
add(m, y + title_h + h + pair_gap, name, 'f')
# Block 2: D=64 and D=32 side by side, top-aligned.
y = top_pad + blk1 + block_gap
x = m
for name, letter, D, clk in CASES[1:]:
    title(x, y, f'({letter}) $D$={D}, {clk} ns')
    add(x, y + title_h, name, 'r')
    axf, _ = add(x, y + title_h + t2 + pair_gap, name, 'f')
    x += E[name]['L'] * S + col_gap
# One scale bar for all panels, in the free space right of (c).
bar_um = 250
x_end = FW - m
yb = y + title_h + t2 + pair_gap / 2
fig.add_artist(plt.Line2D([(x_end - bar_um * S) / FW, x_end / FW], [1 - (yb + 0.02) / FH] * 2, color=fs.INK, lw=1.6,
                          solid_capstyle='butt'))
fig.text((x_end - bar_um * S / 2) / FW, 1 - (yb - 0.005) / FH, f'{bar_um} µm', ha='center', va='bottom',
         fontsize=fs.ANNOT, color=fs.INK)
fig.legend(handles=[Patch(color=SHOWN[n], label=l) for l, n in LABELS], loc='lower center', ncol=3,
           bbox_to_anchor=(0.5, 0.01 / FH), handlelength=1.0, handleheight=0.8, columnspacing=1.0, labelspacing=0.25,
           borderaxespad=0.0, borderpad=0.25, fontsize=fs.ANNOT)
for name, *_ in CASES:
    g = E[name]['g']
    print(name, 'die %.1f x %.1f um' % tuple(g['die_um']), 'cells %.0f um2' % sum(g['area_um2']),
          'scale %.4f in/mm' % (S * 1e3))
print('figure %.2f x %.2f in' % (FW, FH))
fs.save(fig, 'Antiphase', 'asic_layout_r4', dpi=500)
import os
from pathlib import Path
fs.jpeg_compress_pdf((Path(os.environ['FIG_OUT']) if 'FIG_OUT' in os.environ else fs.ROOT / 'Antiphase_DAC27' / 'figures') / 'asic_layout_r4.pdf')
