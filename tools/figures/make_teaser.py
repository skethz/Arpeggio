"""Fig. 1 of Antiphase, a teaser that shows rather than tells (user, 4 Nov 2026: "<instruction>").

Panels follow the Introduction: Background, Challenge, Research Question, Approach, Results.
Data, built from the files only (plain values below are as printed in the paper):
  (a), (b) work/plan_20261024/ap_ber/data/mechanism/mech_traces_{examples,population}.csv, as the previous Fig. 1(b), (c);
           87-99 % and 0.1 %: mech_traces_summary.json.
  (c)      a55/analysis.json, budget B = 1 picks under E and F-R (the rings of Fig. 3(a), (b)); A5.5, 6 Nov 2026.
  (d)      Sections V-B and V-C, Table III (table2.csv; a5/a53.json tab2_*; a5/a5.json a5a.tab2_x32).
  (e)      A5.18 part 2 routed Arpeggio over Chord, both at 1.00 ns: rho_t 0.842744/0.676901, rho_E 0.888282/0.668024
           (work/plan_20261024/antiphase_asic/results_a518/interim_d32_d64.json; PROTOCOL_A518_part2.md 0d0eeeee), since 11 Nov 2026
           (body_sameclock_20261111 preview); before: A5.11 rho_t 0.744/0.780, rho_E 1.021/0.610 (each engine at its own clock),
           since the sequential reframe (9 Nov 2026); it was Table IV's pJ per decision.
  4        Antiphase and first-accept grids are schematic (pale: tested, dark: flipped); 9 Nov 2026.
The grids are schematic: N = 8 spins, D = 4 coordinates, P = 2 copies.
Colours (user, 9 Nov 2026): Antiphase #8C1515, first-accept SA #1966FF, SA #002B49, baselines #53565A and #A0A2A4,
research-question fill #F2F4F7, ours panel #F1E3E3 (were ours #0077C8, panel #E0EFF8).
Writes to out/; copying into figures/ is a separate step.
Names since 9 Nov 2026 (user "Apply it"): Chord (was Antiphase), Arpeggio (first-accept SA on our engine); work/rename_chord_arpeggio_20261109/.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / 'work' / 'plan_20261024' / 'ap_ber' / 'data'
OURS, NAVY, DARK, MID, PALE, LIGHT, TINT, INK = '#8C1515', '#002B49', '#53565A', '#A0A2A4', '#CBCCCD', '#F2F4F7', '#F1E3E3', '#000000'
# User palette of 9 Nov 2026: Antiphase #8C1515 (OURS, was #0077C8; TINT its 12% tint, was #E0EFF8), first-accept SA #1966FF (FA).
FA = '#1966FF'
W, H = 252.0, 248.1   # printed size in pt (panel 3 box 3 pt lower since 10 Nov 2026, user)
TXT, HEAD = 7.0, 8.0

plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['Times New Roman', 'Times', 'STIXGeneral'], 'mathtext.fontset': 'stix',
    'font.size': TXT, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.linewidth': 0.5, 'axes.edgecolor': DARK,
    'xtick.color': DARK, 'ytick.color': DARK, 'xtick.major.width': 0.5, 'ytick.major.width': 0.5,
    'xtick.minor.width': 0.4, 'ytick.minor.width': 0.4, 'xtick.major.size': 2, 'ytick.major.size': 2,
    'xtick.minor.size': 1.2, 'ytick.minor.size': 1.2, 'xtick.major.pad': 1.2, 'ytick.major.pad': 1.2,
    'xtick.labelsize': TXT, 'ytick.labelsize': TXT, 'xtick.direction': 'out', 'ytick.direction': 'out',
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.labelsize': TXT, 'axes.labelpad': 1.5,
})

fig = plt.figure(figsize=(W / 72, H / 72))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(H, 0)     # y runs down, in printed points
ax.axis('off')


def t(x, y, s, **kw):
    kw.setdefault('fontsize', TXT)
    kw.setdefault('va', 'center')
    return ax.text(x, y, s, color=kw.pop('color', INK), **kw)


def runs(x, y, parts, **kw):
    """Text runs on one line: parts are (string, dict of text properties). Returns the end x."""
    r = fig.canvas.get_renderer()
    for s, p in parts:
        o = t(x, y, s, **{**kw, **p})
        x = o.get_window_extent(r).transformed(ax.transData.inverted()).x1 + (TXT * 0.25 if s.endswith(' ') else 0)
    return x


def box(x, y, w, h, fc='white', ec=None, lw=0.5, r=1.5, z=1, ls='-'):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', fc=fc,
                                ec=ec if ec else 'none', lw=lw, zorder=z, ls=ls))


def arrow(x0, y0, x1, y1, color=DARK, lw=0.6, ms=4.0, z=3):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle='-|>', mutation_scale=ms, lw=lw, color=color,
                                 shrinkA=0, shrinkB=0, zorder=z))


def badge(y, n):
    box(0.4, y - 4.1, 8.2, 8.2, fc=INK, r=1.3, z=3)
    t(4.5, y + 0.1, str(n), ha='center', color='white', fontweight='bold', zorder=4)


def head(y, n, label, rest):
    badge(y, n)
    return runs(11, y, [(label + ': ', dict(fontweight='bold')), (rest, dict(fontweight='bold'))], fontsize=HEAD)


CW, CH, GAP = 7.0, 2.1, 1.2
D, P = 4, 2
N = D * P
GRID_H = N * CH + (D - 1) * GAP


def grid(x, y, active, col, off=LIGHT):
    """Rows: the P copies of each of D coordinates, a small gap between coordinates. Columns: steps."""
    for m in range(D):
        for c in range(P):
            yy = y + (m * P + c) * CH + m * GAP
            for k in range(8):
                ax.add_patch(Rectangle((x + k * CW, yy), CW - 0.7, CH - 0.45, fc=col if active(m, c, k) else off,
                                       ec='none', zorder=2))


def gauge(x, y, n, col, track=LIGHT):
    """Spins that decide per step, out of N, on a bar as wide as the grid less its label."""
    w = 8 * CW - 14
    ax.add_patch(Rectangle((x, y - 1.5), w, 3, fc=track, ec='none', zorder=2))
    ax.add_patch(Rectangle((x, y - 1.5), w * n / N, 3, fc=col, ec='none', zorder=3))
    t(x + 8 * CW - 0.7, y, f'{n}/{N}', ha='right', color=DARK)


sync = lambda m, c, k: True
seq = lambda m, c, k: k % N == m * P + c
# An exact coloring of N dense spins: orthogonal in-phase and quadrature copies of one user share a phase (N/2 phases).
color = lambda m, c, k: k % (N // 2) == (m // 2) * P + c
anti = lambda m, c, k: k % P == c

# --- 1 Background ---------------------------------------------------------------------------------------------------
y = 4.6
head(y, 1, 'Background', 'detectors use parallel hardware')   # T16, 9 Nov 2026: hardware, not problem-level (was 'detectors run in parallel', sequential reframe)
yl = y + 8.7
yd = yl + 7.9
yg = yd + 10.8


def step(x, name, desc):
    """A step: method name, then what the method does."""
    t(x, yl, name, fontweight='bold')
    t(x, yd, desc)


# Step 1: mixed signals reach the base station; the optimum searches every candidate.
step(0, 'Exact ML', 'search $16^{32}$ candidates')
for i, (dy, col) in enumerate(((-6, DARK), (0, MID), (6, DARK))):
    box(0.8, yg + dy - 2.2, 3.6, 4.4, fc='white', ec=DARK, r=0.8)
    xs = np.linspace(5.2, 42, 80)
    u = (xs - 5.2) / (42 - 5.2)
    ax.plot(xs, yg + dy * (1 - u) + 1.5 * np.sin(2 * np.pi * (2.4 + 0.5 * i) * u + i) * (0.35 + 0.65 * u), color=col, lw=0.45, zorder=1)
ax.plot([44.5, 44.5], [yg - 6.5, yg + 7.2], color=INK, lw=0.8, solid_capstyle='butt')
ax.add_patch(Polygon([[41.5, yg - 7.2], [47.5, yg - 7.2], [44.5, yg - 3.4]], closed=True, fc=INK, ec='none', zorder=2))
t(51, yg - 3.7, '32 users,')
t(51, yg + 3.7, '16-QAM')
# Step 2: MDI-MIMO searches a correction d around a guess x_g, each d_m a sum of P spin copies (Section II-A).
# MMSE-SIC left out of the teaser, more room here (user, 5 Nov 2026). Schematic: P = 4, the 16-QAM levels -3, -1, +1, +3.
bx0 = 88
runs(bx0, yl, [('MDI-MIMO: ', dict(fontweight='bold')), ('correct a guess, minimizing $\\|y-Hx\\|^2$', {})])
LX = lambda lev: 173.5 + (lev + 3) * 9.2
for ys, spins, dlab, g0, g1 in ((yg - 11.0, (1, 1, -1, 1), '$d_1=+2$', -1, 1), (yg - 3.0, (-1, 1, -1, -1), '$d_2=-2$', 3, 1)):
    for i, s_ in enumerate(spins):
        x = bx0 + 3.2 + i * 7.6
        ax.add_patch(Circle((x, ys), 3.1, fc='white', ec=INK, lw=0.5, zorder=3))
        arrow(x, ys + 2.1 * s_, x, ys - 2.2 * s_, color=INK, lw=0.5, ms=3.0, z=4)
    arrow(bx0 + 30.5, ys, bx0 + 35.5, ys)
    t(bx0 + 36.5, ys + 0.75, '$\\Sigma$', fontsize=8.5, zorder=4)
    arrow(bx0 + 43, ys, bx0 + 48, ys)
    t(bx0 + 49, ys - 0.1, dlab, zorder=4)
    arrow(bx0 + 74, ys, bx0 + 79, ys)
    # The coordinate's four constellation levels: the guess moves by the summed correction.
    ax.plot([LX(-3) - 3, LX(3) + 3], [ys, ys], color=MID, lw=0.5, zorder=1)
    for lev in (-3, -1, 1, 3):
        ax.plot([LX(lev), LX(lev)], [ys - 1.4, ys + 1.4], color=MID, lw=0.5, zorder=1)
    ax.add_patch(Circle((LX(g0), ys), 1.8, fc='white', ec=INK, lw=0.5, zorder=4))
    ax.add_patch(Circle((LX(g1), ys), 1.8, fc=INK, ec=INK, lw=0.5, zorder=4))
    sgn = 1 if g1 > g0 else -1
    arrow(LX(g0) + sgn * 2.2, ys, LX(g1) - sgn * 2.2, ys, color=INK, lw=0.5, ms=3.0, z=3)
yl2 = yg + 4.6
t(bx0, yl2, '$P$ Ising spins')
t(bx0 + 49, yl2, 'correction')
ax.add_patch(Circle((LX(-3) - 1, yl2), 1.8, fc='white', ec=INK, lw=0.5, zorder=4))
t(LX(-3) + 2, yl2, 'guess')
ax.add_patch(Circle((LX(-3) + 22.5, yl2), 1.8, fc=INK, ec=INK, lw=0.5, zorder=4))
t(LX(-3) + 25.5, yl2, 'guess $+\\,d$')
t(W, yg - 7.0, 'levels', ha='right', color=DARK)

# --- 2 Challenge ----------------------------------------------------------------------------------------------------
y = yg + 13.0
head(y, 2, 'Challenge', 'no remedy separates only the copies')
ax.add_patch(Rectangle((W - 30.5, y - 1.2), 6.3, 2.2, fc=DARK, ec='none', zorder=2))
t(W, y, 'decides', ha='right', color=DARK)
gx = [25, 103.5, 178.5]
yn = y + 8.7
# 'colors', not 'phases', as in the text (round-3 audit 3.3, 8 Nov 2026)
# 'P colors/user', not 'N/2 colors': N is defined only in Section II-A (round-7 review R7.15, 8 Nov 2026)
for x, nm, rest in zip(gx, ('Synchronous: ', 'Sequential SA: ', 'Coloring: '),
                       ('two-cycles', 'one spin', '$P$ colors/user')):
    runs(x, yn, [(nm, dict(fontweight='bold')), (rest, {})])
y1 = yn + 4.3
for x, act, col, n in zip(gx, (sync, seq, color), (MID, NAVY, DARK), (8, 1, 2)):
    grid(x, y1, act, col)
    gauge(x, y1 + GRID_H + 4.2, n, col)
t(0, y1 + GRID_H / 2, 'spins', color=DARK)
t(0, y1 + GRID_H + 4.2, 'parallel', color=DARK)
t(0, yn, 'step →', color=DARK)

# --- 3 Research Question --------------------------------------------------------------------------------------------
y = y1 + GRID_H + 8.0
qh = 16.6   # was 19.6 (user, 10 Nov 2026: shrink panel 3 box to gain a line)
box(0, y, W, qh, fc=LIGHT, r=1.5)
badge(y + qh / 2, 3)
qy = y + qh / 2
runs(11, qy, [('Research Question: ', dict(fontweight='bold')),
              ('Must MIMO detectors flip in parallel?', dict(fontstyle='italic'))], fontsize=HEAD)   # sequential reframe (user, 9 Nov 2026)

# --- 4 Approach -----------------------------------------------------------------------------------------------------
y = y + qh + 1.8
ah = 41.3
box(0, y, W, ah, fc=TINT, r=1.5)
ytop4 = y
y = y + 5.2
# Sequential reframe, phase 2 (9 Nov 2026): panel 4 sets Antiphase (best-case parallel flips) beside first-accept SA on the same
# tests (Section V-B; Witte 1991, Sohn 1995). Schematic, N = 8 spins: pale cells are tested, dark cells flip; both test one copy's D = 4 spins
# per step (gauge 4/8). Antiphase flips every passing spin; first-accept flips the first passing one, re-tests, and keeps the copy until none passes.
# 11 Nov 2026 (number check, checker a): Arpeggio re-tests only the spins after the flipped one, with no re-test after a flip on the copy's
# last spin, each copy once per sweep (Section III-C, C_FA). The re-test columns now show only those spins; the gauge's 4/8 is a pass's first test.
head(y, 4, 'Approach', 'on our engine, Chord vs. Arpeggio')   # engine reframe v4, 9 Nov 2026 (reviewer 2 F7)
y2 = y + 6.2
yb = y2 + GRID_H + 4.2
PALE_O, PALE_F = '#D8AFAF', '#B1CBFF'   # 34% tints of OURS and FA for tested-only cells (were #A9D0EC, navy #AEBBC6)
AP_FLIP = ({0, 2, 3}, {1, 2}, {0, 3}, {1}, {2}, {0}, set(), {3})   # flips per half-step, falling as the anneal settles
FA_C = (0, 0, 1, 1, 0, 0, 1, 0)                                    # copy tested at each step
FA_LO = (0, 2, 0, 1, 0, 3, 0, 0)                                   # first coordinate tested (re-tests start after the flip)
FA_M = (1, 3, 0, None, 2, None, None, None)                        # its first passing coordinate, if any


def grid2(x, tested, flipped, pale, dark):
    for m in range(D):
        for c in range(P):
            yy = y2 + (m * P + c) * CH + m * GAP
            for k in range(8):
                fc = dark if flipped(m, c, k) else (pale if tested(m, c, k) else 'white')
                ax.add_patch(Rectangle((x + k * CW, yy), CW - 0.7, CH - 0.45, fc=fc, ec='none', zorder=2))


grid2(gx[0], anti, lambda m, c, k: anti(m, c, k) and m in AP_FLIP[k], PALE_O, OURS)
# One half-step: every coordinate still decides.
ax.add_patch(Rectangle((gx[0] + 2 * CW - 0.5, y2 - 0.8), CW + 0.3, GRID_H + 1.2, fc='none', ec=INK, lw=0.5, zorder=4))
gauge(gx[0], yb, 4, OURS, track='white')
t(1, y2 + GRID_H / 2, 'spins', color=DARK)
t(1, yb, 'parallel', color=DARK)
# Pinning: a flip penalty raises the barrier a spin must cross (narrowed to make room for the first-accept grid).
pc, py = 104, y2 + GRID_H / 2
t(84, py, '+', fontsize=9, ha='left', fontweight='bold')
u = np.linspace(-1.25, 1.25, 80)
ax.plot(pc + 10 * u, py - 0.4 + 7.2 * (u ** 2 - 1) ** 2 * -1 + 7.2, color=INK, lw=0.6, zorder=3)
ax.add_patch(Circle((pc - 10, py + 4.2), 1.9, fc=OURS, ec='none', zorder=4))
arrow(pc, py - 0.9, pc, py - 7.4, color=INK, lw=0.5, ms=3.0)
t(pc + 2.2, py - 4.6, '$q$')
t(pc, yb, 'pinning', ha='center')
x2g = 127
grid2(x2g, lambda m, c, k: c == FA_C[k] and m >= FA_LO[k], lambda m, c, k: c == FA_C[k] and m == FA_M[k], PALE_F, FA)
gauge(x2g, yb, 4, FA, track='white')
ex = 188.5
t(ex, y2 + 1.4, 'Flips per test:', color=DARK)
runs(ex, y2 + 9.6, [('Chord: ', dict(fontweight='bold')), ('all', {})])
runs(ex, y2 + 17.8, [('Arpeggio: ', dict(fontweight='bold')), ('one', {})])
t(ex, yb, '1 cycle per flip')

# --- 5 Results ------------------------------------------------------------------------------------------------------
y = ytop4 + ah + 6.2
xe = head(y, 5, 'Results', 'no gain from flipping all')   # sequential reframe, 9 Nov 2026; 'per test' since engine reframe v3 (reviewer 1);
# 'one per test beats all' since 11 Nov 2026 (user "Revert and fix"): PROTOCOL_A514 sec. 9 (mixed) allows no claim that one flip per test
# is necessary, so the heading names the comparison made, Arpeggio (one) vs. Chord (all), as panel 4's 'Flips per test' does.
# 'no gain from flipping all' since 11 Nov 2026 (blind round c, HW and MIMO: 'beats all' overstates P2's 1.03x); matches Table I 'No flip gain'.
lx = 137
# keys moved left 1.5 and 2 so the SA key fits a dot and a diamond (round-6 review 19, 8 Nov 2026)
# Chord/Arpeggio preview (9 Nov 2026): Arpeggio (first-accept SA on our engine) gets its own key, a blue diamond; SA keeps the dot.
# Keys are spaced by measured text ends, with the old gap (6.3 pt) between a label and the next key.
_rr = fig.canvas.get_renderer()
_keys = (('synchronous', MID, 'line'), ('Chord', OURS, 'line'), ('SA', NAVY, 'dot'), ('Arpeggio', FA, 'diamond'))
_tw = []
for lab, col, kind in _keys:
    _o = t(0, y, lab); _e = _o.get_window_extent(_rr).transformed(ax.transData.inverted()); _tw.append(_e.x1 - _e.x0); _o.remove()
_kw = sum((3.8 if k != 'line' else 6.3) for _, _, k in _keys) + sum(_tw)
_gap = min(6.3, (251.5 - (xe + 6.3) - _kw) / (len(_keys) - 1))   # right-aligned at 251.5; gap shrinks only if needed
lx = 251.5 - _kw - _gap * (len(_keys) - 1)
print('results head ends at %.1f, legend starts at %.1f, gap %.2f' % (xe, lx, _gap))
for lab, col, kind in (('synchronous', MID, 'line'), ('Chord', OURS, 'line'), ('SA', NAVY, 'dot'), ('Arpeggio', FA, 'diamond')):
    if kind == 'dot':   # SA is drawn as dots in (c) and (d); navy triangles in (d) are MDI-MIMO
        ax.plot([lx + 1.0], [y], 'o', ms=2.4, color=NAVY)
    elif kind == 'diamond':   # Arpeggio diamond in blue, as in (c), (e) and Fig. 3
        ax.plot([lx + 1.0], [y], 'D', ms=2.3, mfc=FA, mec=FA, mew=0.5)
    else:
        ax.plot([lx, lx + 5], [y, y], color=col, lw=1.2, solid_capstyle='butt')
    _o = t(lx + (3.8 if kind != 'line' else 6.3), y, lab, color=INK)
    lx = _o.get_window_extent(_rr).transformed(ax.transData.inverted()).x1 + _gap
print('legend ends at %.1f of %.1f pt' % (lx - _gap, W))


def axes(x0, x1, pt, pb):
    return fig.add_axes([x0 / W, 1 - pb / H, (x1 - x0) / W, (pb - pt) / H])


PH = 26.8
ya = y + 8.7
runs(0, ya, [('(a) Returns: 87–99% → ', {}), ('0.1%', dict(fontweight='bold'))])
t(90, ya, '(b) Energy gap to truth')
t(170, ya, '(c) SA at no more cycles')   # A5.5: SA re-tuned per budget, best pick within Antiphase's modeled cycles (B = 1), 6 Nov 2026
pt, pb = ya + 4.2, ya + 4.2 + PH

# (a) one sub-problem, K = 2, dimensions and offsets of the previous Fig. 1(b)
ex = defaultdict(list)
with open(ROOT / 'mechanism' / 'mech_traces_examples.csv') as f:
    for r in csv.DictReader(f):
        if r['K'] == '2' and r['example'] == '0' and r['variant'] in ('alternation', 'no_alternation'):
            ex[r['variant']].append(r)
for v in ex:
    ex[v].sort(key=lambda r: int(r['half_step']))
T = 10
ax_a = axes(11, 80, pt, pb)
for variant, cols, lws, z in (('no_alternation', (MID, MID, MID), (0.55, 0.55, 0.55), 2), ('alternation', (OURS,) * 3, (1.1,) * 3, 3)):
    for j, m in enumerate((2, 3, 7)):
        rows = ex[variant][:T + 1]
        ax_a.plot([int(r['half_step']) for r in rows], [float(r[f'd{m}']) / 2 + 0.07 * (j - 1) for r in rows],
                  color=cols[j], lw=lws[j], zorder=z)
ax_a.set_xlim(0, T)
ax_a.set_ylim(-2.4, 2.4)
ax_a.set_yticks([-2, 0, 2])
ax_a.set_yticklabels(['−2', '0', '2'])
ax_a.set_xticks([0, T])

# (b) mean of 200 sub-problems, K = 1
pop = defaultdict(lambda: ([], []))
with open(ROOT / 'mechanism' / 'mech_traces_population.csv') as f:
    for r in csv.DictReader(f):
        if r['K'] == '1':
            pop[r['variant']][0].append(int(r['half_step']))
            pop[r['variant']][1].append(float(r['mean_energy_gap_to_truth']))
ax_b = axes(103, 162, pt, pb)   # 4 pt narrower (was 166) so (c)'s BER label sits nearer (c) than (b) (user, 5 Nov 2026)
for key, col, ls, lw in (('no_alternation', MID, '-', 0.8), ('no_alternation_q0', MID, ':', 0.8),
                         ('alternation_q0', OURS, (0, (2.5, 1)), 0.7), ('alternation', OURS, '-', 1.1)):
    tt, g = (np.array(a) for a in pop[key])
    ax_b.plot(tt[1:], g[1:], color=col, ls=ls, lw=lw)
ax_b.set_xscale('log')
ax_b.set_yscale('log')
ax_b.set_xlim(1, 256)
ax_b.set_ylim(0.12, 600)
ax_b.set_yticks([1, 100])
ax_b.set_xticks([1, 100])
ax_b.minorticks_off()
ax_b.text(250, 11, 'no pinning', ha='right', va='bottom', fontsize=TXT)

# (c) SA within Antiphase's modeled cycles (A5.5, PROTOCOL_A55 sec. 9, budget B = 1), the rings of Fig. 3(a), (b):
#     x = users (16, 32); one line per SA hardware: serial HW (one comparator, Eq. (4)) and Antiphase HW (first-accept with rule (2)
#     on Antiphase's D comparators); Antiphase is the blue line at 1x (user, 6 Nov 2026: earlier dot pairs and 'serial HW' x labels were unclear).
A55 = json.load(open(ROOT / 'a55' / 'analysis.json'))['points']
# users on x; one line per SA hardware, labelled in place; Antiphase is the blue line at 1 (legend: blue line) (6 Nov 2026)
ax_c = axes(186, 250, pt, pb)
# Highlight follows the headline (user "Apply all three", 9 Nov 2026): first-accept, the winner, has its own colour (FA);
# Antiphase is the 1x line in its own colour (user, 9 Nov 2026: the gray line was confusing); one-comparator SA stays navy.
REF_KW = dict(color=OURS, lw=0.9, zorder=1)
ax_c.axhline(1, **REF_KW)
XU = {'P1': 0, 'P2': 1}
# first-accept (rule (2)) is a filled diamond as in Fig. 3; an open ring there means a budget pick (round-3 audit 5.2, 8 Nov 2026)
# first-accept dotted: dashed blue is (b)'s Antiphase without pinning
for key, mk, ms, ls, col in (('E/1', 'o', 2.6, '-', NAVY), ('F-R/1', 'D', 2.3, (0, (1, 1.2)), FA)):
    xs = [XU[P] for P in ('P1', 'P2')]
    ys = [A55[P]['budget'][key]['ratio'] for P in ('P1', 'P2')]
    # no interval bars: at this height they hide behind the markers; Fig. 3 carries the CIs
    ax_c.plot(xs, ys, color=col, lw=0.6, ls=ls, zorder=2)
    ax_c.plot(xs, ys, mk, ms=ms, mfc=col, mec=col, mew=0.5, ls='none', zorder=3)
ax_c.set_yscale('log')
ax_c.set_xlim(-0.25, 1.25)
ax_c.set_ylim(0.06, 50)
ax_c.set_xticks([0, 1])
ax_c.set_xticklabels(['16', '32'])
ax_c.set_yticks([1, 10])
ax_c.set_yticklabels(['1\u00d7', '10\u00d7'])   # a ratio to Antiphase, not a raw BER
ax_c.minorticks_off()
e1, e2 = A55['P1']['budget']['E/1']['ratio'], A55['P2']['budget']['E/1']['ratio']
f1, f2 = A55['P1']['budget']['F-R/1']['ratio'], A55['P2']['budget']['F-R/1']['ratio']
_r = fig.canvas.get_renderer()
def _pair(x, y, a, b, sz=6.0):
    """Regular a then bold b, centred together at (x, y) in data coordinates."""
    o1 = ax_c.text(0, y, a, fontsize=sz, color=INK, ha='left', va='center')
    o2 = ax_c.text(0, y, b, fontsize=sz, fontweight='bold', color=INK, ha='left', va='center')
    inv = ax_c.transData.inverted()
    w1 = o1.get_window_extent(_r).width; w2 = o2.get_window_extent(_r).width
    xd = ax_c.transData.transform((x, y))[0] - (w1 + w2) / 2
    o1.set_x(inv.transform((xd, 0))[0]); o2.set_x(inv.transform((xd + w1, 0))[0])
_pair(0.5, 22, 'one comparator ', '%.1f–%.1f×' % (e1, e2))
_pair(0.5, 0.13, 'Arpeggio ', '%.2f–%.2f×' % (f1, f2))
# the 1x line is Antiphase (caption: SA's BER over Antiphase's); no in-plot label (it crowded the one-comparator line)

ax_c.text(-0.27, 0.5, 'BER ratio', transform=ax_c.transAxes, rotation=90, ha='center', va='center', fontsize=TXT, color=DARK)   # centred, next to (c)'s ticks (user, 5 Nov 2026)
for a, lab, fx in ((ax_a, 'round', 0.5), (ax_b, 'round', 0.5), (ax_c, 'users', 0.5)):   # 'round', was 'half-step' (user, 10 Nov 2026; work/round_rename_20261110)
    a.text(fx, -0.07, lab, transform=a.transAxes, ha='center', va='top', fontsize=TXT, color=DARK)

# --- second row -------------------------------------------------------------------------------------------------
yb2 = pb + 15.2
t(0, yb2, '(d) Chord SNR lead, dB; one mark per setting')
t(251.5, yb2, '(e) Routed Arpeggio', ha='right')   # was '(e) 2.7-3.6 pJ/spin decision' (sequential reframe, 9 Nov 2026); right-aligned to fit
pt2, pb2 = yb2 + 4.2, yb2 + 4.2 + PH

ax_d = axes(53, 130, pt2, pb2)
# Colour and marker follow each method in Figs. 3 and 4 (user, 5 Nov 2026): MDI navy triangle, K-best gray square,
# SA navy circle. Right of zero, tinted: Antiphase needs less SNR. Numbers sit in one column, signed.
# Row names put the user count first ('32-user K-best'), so 32 is not read as K-best's candidate count (round-8 audit A3.3, 8 Nov 2026).
rows = [
    ('MDI-MIMO, $10^{-3}$', [0, 1.35, 0.5], NAVY, '^', '0 to +1.35'),   # published curves, Section V-C; 0.25 unresolved, drawn at 0 (blind review 8 Nov 2026; exactly 0 since round 7)
    ('32-user K-best', [2.23, 1.70, 0.98, 0.78], DARK, 's', '+0.78 to +2.23'),   # paired, table2_pairs.csv: 16-QAM 2.23/1.70, QPSK 0.98/0.78 (QPSK added 8 Nov 2026)
    ('16-user K-best', [0, -1.60, 0, -0.07], DARK, 's', '0 to \u22121.60'),   # paired (table2_pairs.csv): 16-QAM 10^-3 unresolved (0), 10^-4 -1.60; QPSK 10^-3 unresolved (0), 10^-4 -0.07 [-0.17, -0.01]
    ('SA, equal sweeps', [-0.44, -1.40, -1.27, -0.88], NAVY, 'o', '\u22120.44 to \u22121.40'),   # a5/a53.json tab2_*, a5/a5.json a5a.tab2_x32
]
ax_d.axvspan(0, 2.6, fc=TINT, ec='none', zorder=0)   # Antiphase's tint (was '#E0EFF8')
for i, (lab, vals, col, mk, num) in enumerate(rows):
    # One marker per condition, joined by a thin line: a range, not a bar from zero.
    ax_d.plot([min(vals), max(vals)], [i, i], color=col, lw=0.6, solid_capstyle='butt', zorder=3)
    # Marks closer than one marker width (0.2 dB) are stacked vertically so that every setting shows (round-7 audit A5.2, 8 Nov 2026).
    order = sorted(range(len(vals)), key=lambda j: vals[j])
    groups, ys = [[order[0]]], [float(i)] * len(vals)
    for j in order[1:]:
        if vals[j] - vals[groups[-1][-1]] >= 0.2:
            groups.append([])
        groups[-1].append(j)
    for g in groups:
        for k, j in enumerate(g):
            ys[j] = i + (k - (len(g) - 1) / 2) * 0.4
    ax_d.plot(vals, ys, mk, ms=3.2, mfc=col, mec='white', mew=0.3, zorder=4, clip_on=False, ls='none')
    yy = pt2 + (i + 0.5) * PH / len(rows)
    t(0, yy, lab)
    t(133, yy, num)
ax_d.axvline(0, color=INK, lw=0.5, zorder=2)
ax_d.set_ylim(len(rows) - 0.5, -0.5)
ax_d.set_xlim(-2.1, 2.6)
ax_d.set_yticks([])
ax_d.spines['left'].set_visible(False)
ax_d.set_xticks([-2, 0, 2])
ax_d.set_xticklabels(['\u22122', '0', '+2'])
for xx, word in ((-1, 'behind'), (1, 'ahead')):
    ax_d.text(xx, -0.07, word, transform=ax_d.get_xaxis_transform(), ha='center', va='top', fontsize=TXT, color=DARK)

# (e) Routed GF22 Arpeggio over Chord per detection, both at 1.00 ns since 11 Nov 2026 (A5.18 part 2); was A5.11 (7 Nov 2026; work/plan_20261024/antiphase_asic/RESULTS_A511.md
#     sec. 4: rho_t 0.744 / 0.780, rho_E 1.021 / 0.610 at P1 (16 users) / P2 (32 users)); Section V-B. Replaces the pJ bars (sequential reframe, 9 Nov 2026).
ax_e = axes(203, 223, pt2, pb2)
ax_e.axhline(1, **REF_KW)   # Antiphase's line at 1x, first-accept in FA (9 Nov 2026, as (c))
# Same-clock pair (A5.18 part 2, 11 Nov 2026): both curves end within 0.01 at 32 users, so the labels no longer sit at the
# line ends; each carries its own line and marker sample on the right, as a two-row key (time above energy).
for vals, ls, mfc, lab, ykey in (((0.842744, 0.676901), '-', FA, 'time', 0.88), ((0.888282, 0.668024), (0, (1, 1.2)), 'white', 'energy', 0.70)):
    # thin lines (0.6 pt, the legend's Antiphase line is 1.2 pt); the panel title names first-accept
    ax_e.plot([0, 1], vals, color=FA, lw=0.6, ls=ls, zorder=2)
    ax_e.plot([0, 1], vals, 'D', ms=2.3, mfc=mfc, mec=FA, mew=0.6, ls='none', zorder=3, clip_on=False)
    ax_e.plot([1.36, 1.66], [ykey, ykey], color=FA, lw=0.6, ls=ls, clip_on=False)
    ax_e.plot([1.51], [ykey], 'D', ms=2.3, mfc=mfc, mec=FA, mew=0.6, ls='none', clip_on=False)
    ax_e.text(1.75, ykey, lab, ha='left', va='center', fontsize=TXT, color=INK, clip_on=False)
ax_e.set_xlim(-0.3, 1.3)
ax_e.set_ylim(0.5, 1.12)
ax_e.set_yticks([0.6, 1])
ax_e.set_yticklabels(['0.6×', '1×'])
ax_e.set_xticks([0, 1])
ax_e.set_xticklabels(['16', '32'])
ax_e.text(1.12, -0.07, 'users', transform=ax_e.transAxes, ha='left', va='top', fontsize=TXT, color=DARK)   # right of 32: the axis is too narrow to centre it


end = pb2 + 9
print(f'content ends at {end:.1f} of {H:.1f} pt')
meta = {'Author': '', 'Creator': '', 'Producer': '', 'Title': 'teaser'}
fig.savefig(HERE / 'out' / 'teaser.pdf', metadata=meta)
fig.savefig(HERE / 'out' / 'teaser.png', dpi=400)

r = fig.canvas.get_renderer()
items = []
for a in (ax, ax_a, ax_b, ax_c, ax_d, ax_e):
    for o in a.texts:
        if o.get_text().strip():
            items.append((o.get_text()[:34], o.get_window_extent(r)))
sx, sy = fig.bbox.width, fig.bbox.height
for s, b in items:
    if b.x0 < -0.5 or b.x1 > sx + 0.5 or b.y0 < -0.5 or b.y1 > sy + 0.5:
        print('OUT OF BOUNDS', s, round(b.x0), round(b.x1), 'of', round(sx), round(b.y1), 'of', round(sy))
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        a, b = items[i][1], items[j][1]
        ox, oy = min(a.x1, b.x1) - max(a.x0, b.x0), min(a.y1, b.y1) - max(a.y0, b.y0)
        if ox > 0.5 and oy > 1.5:
            print('OVERLAP', items[i][0], '|', items[j][0], round(ox, 1), round(oy, 1))
