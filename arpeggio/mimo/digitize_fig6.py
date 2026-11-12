#!/usr/bin/env python3
"""Figure readings of the published Fig. 6 (arXiv:2604.17109v2, page 11; the embedded 1799 x 1301 image extracted with
pdfimages, baselines/pimi_fig6/fig6-000.png) for the PIMI hardware (red) and theoretical-optimal (blue) curves, as a
cross-check that the figure shows the runs whose exact BER is in the authors' report.json files.
Method: per panel, the frame and the tick marks (x: 0..40 dB; y: 1e-1, 1e-2, 1e-3) are found from black pixels; at each
plotted Eb/N0 a hollow '^' template of the plotted marker size (their analysis notebooks: ms 4 pt for the hardware
curve, 3 pt for the 4x curve; 255 dpi; edge about 3.5 px) is matched to the curve colour in a window of +-2 px in x and
+-40 px in y around the line (score: coloured pixels on the outline minus twice those in the interior); the best
match is the reading. A version 1 that took the extent of the coloured run in the marker's column was biased by the
attached line segments (+0.09 decades on the hardware curve) and is replaced. Uncertainty: +-2 px, about +-0.02 decades
at 102 px per decade; markers clipped by the axis bottom (BER below about 2e-4) are not read. Usage: digitize_fig6.py PNG REPORTS.jsonl OUT.jsonl"""
import json
import math
import re
import sys

import numpy as np
from PIL import Image

png, rep_path, out = sys.argv[1:4]
a = np.array(Image.open(png).convert('RGB')).astype(int)
R, G, B = a[..., 0], a[..., 1], a[..., 2]
black = (R < 70) & (G < 70) & (B < 70)
red = (R > 140) & (G < 80) & (B < 80)
blue = (B > 140) & (R < 70) & (G > 70) & (G < 160)
# approximate frames (x0, y0, x1, y1) by eye; refined below
APPROX = {'a': (265, 67, 675, 413), 'b': (800, 67, 1208, 413), 'c': (1325, 67, 1733, 413),
          'd': (265, 640, 675, 988), 'e': (800, 640, 1208, 988), 'f': (1325, 640, 1733, 988)}
PANEL = {'a': (8, 4), 'b': (8, 16), 'c': (8, 64), 'd': (16, 4), 'e': (16, 16), 'f': (16, 64)}
HW = {(8, 4): 16, (8, 16): 32, (8, 64): 64, (16, 4): 32, (16, 16): 64, (16, 64): 64}
TO = {(8, 4): 64, (8, 16): 128, (8, 64): 256, (16, 4): 128, (16, 16): 256, (16, 64): 256}


def refine(x0, y0, x1, y1):
    def best_row(lo, hi):
        return max(range(lo, hi), key=lambda y: black[y, x0 + 20:x1 - 20].sum())

    def best_col(lo, hi):
        return max(range(lo, hi), key=lambda x: black[y0 + 20:y1 - 20, x].sum())
    return best_col(x0 - 8, x0 + 8), best_row(y0 - 8, y0 + 8), best_col(x1 - 8, x1 + 8), best_row(y1 - 8, y1 + 8)


def template(size, edge):
    """Outline and interior masks of matplotlib's '^' marker (vertices (0, 1), (-1, -1), (1, -1) x size/2), centred."""
    h = int(size / 2 + edge) + 2
    yy, xx = np.mgrid[-h:h + 1, -h:h + 1].astype(float)
    # half-planes of the triangle in image coordinates (y down): base y <= size/2, sides through the apex (0, -size/2)
    def inside(d):
        r = size / 2 + d
        return (yy <= r) & (2 * np.abs(xx) - yy <= r + d * (np.sqrt(5) - 1))
    outer, inner = inside(edge / 2), inside(-edge / 2)
    return outer & ~inner, inner


def match(mask, px, yp, size, edge, y_lo, y_hi):
    ol, il = template(size, edge)
    h = ol.shape[0] // 2
    best = None
    for x in range(px - 2, px + 3):
        for y in range(max(int(yp) - 40, y_lo + h), min(int(yp) + 41, y_hi - h)):
            w = mask[y - h:y + h + 1, x - h:x + h + 1]
            sc = int(w[ol].sum()) - 2 * int(w[il].sum())
            if best is None or sc > best[0]:
                best = (sc, x, y)
    return best


def clusters(idx, gap):
    out, cur = [], []
    for v in idx:
        if cur and v - cur[-1] > gap:
            out.append(cur); cur = []
        cur.append(v)
    if cur:
        out.append(cur)
    return out


rep = {}
for l in open(rep_path):
    r = json.loads(l)
    m = re.search(r'Nt(\d+)_Nr\d+_(\d+)QAM/(\d+)/tanh_lut_4/16_precision/(\d+)_steps_32_anneals', r['path'])
    if m:
        rep[tuple(map(int, m.groups()))] = r['report']
fo = open(out, 'w')
for p, (nt, M) in PANEL.items():
    xl, yt, xr, yb = refine(*APPROX[p])
    # x ticks below the bottom frame, y ticks left of the left frame
    xt = [int(np.mean(c)) for c in clusters(np.nonzero(black[yb + 3:yb + 9, xl - 5:xr + 5].any(0))[0] + xl - 5, 2)]
    yt_ = [int(np.mean(c)) for c in clusters(np.nonzero(black[yt + 3:yb - 3, xl - 9:xl - 3].any(1))[0] + yt + 3, 2)]
    if len(xt) != 5 or len(yt_) != 3:
        print('panel', p, 'tick detection failed', xt, yt_); continue
    xs = np.polyfit([0, 10, 20, 30, 40], xt, 1)
    ys = np.polyfit([-1, -2, -3], yt_, 1)
    dec = abs(ys[0])
    for curve, mask, steps in (('HW', red, HW[(nt, M)]), ('TO', blue, TO[(nt, M)])):
        for (nt_, M_, snr, st), t in sorted(rep.items()):
            if (nt_, M_, st) != (nt, M, steps):
                continue
            plotted = min(t['ber'], t['ber_mmse'])                       # their 'report_ber'
            if plotted <= 0:
                continue
            px = int(round(np.polyval(xs, snr)))
            yp = np.polyval(ys, math.log10(plotted))
            size = (4.0 if curve == 'HW' else 3.0) * 255 / 72
            rec = dict(panel=p, nt=nt, M=M, curve=curve, steps=steps, ebn0=snr, ber_report=t['ber'], plotted_report=plotted,
                       px_per_decade=dec)
            bm = None if yp > yb - size / 2 - 2 else match(mask, px, yp, size, 3.5, yt + 2, yb - 2)
            ol, _ = template(size, 3.5)
            if bm is None or bm[0] < 0.5 * ol.sum():
                rec.update(read=None, note='clipped by the axis bottom or no marker found')
            else:
                yc = bm[2]
                lg = (yc - ys[1]) / ys[0]
                rec.update(read=10 ** lg, read_lo=10 ** (lg + 2 / dec), read_hi=10 ** (lg - 2 / dec),
                           offset_decades=lg - math.log10(plotted), score=bm[0], score_max=int(ol.sum()))
            fo.write(json.dumps(rec) + '\n')
            print(json.dumps(rec))
