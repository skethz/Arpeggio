"""Helpers for the ASIC layout figures: cropped Innovus routed views and RTL-function maps.

Routed views are square Innovus dumps framed on the die (zoomBox), cropped here to the die's bright extent.
Function maps come from the server-side aggregate raster: per pixel, the RTL function group with the most placed
cell area, shaded by local cell occupancy. Physical-only instances (fillers, taps, decaps) are excluded.
"""
import json
import numpy as np
from PIL import Image
from matplotlib.colors import to_rgb
import figstyle as fs

Image.MAX_IMAGE_PIXELS = None


def routed_view(png, die_um, max_px=1100, lift=1.15, gamma=0.92):
    """Crop a square die-framed dump to the die and return (rgb array, extent in um)."""
    im = Image.open(png).convert('RGB')
    a = np.asarray(im)
    mask = a.max(2) > 24
    rows, cols = np.where(mask.any(1))[0], np.where(mask.any(0))[0]
    a = a[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    # Pins sit just outside the die; trim to the die aspect around the center of the bright region.
    h, w = a.shape[:2]
    want = die_um[0] / die_um[1]
    if w / h > want * 1.01:
        nw = int(round(h * want)); x0 = (w - nw) // 2; a = a[:, x0:x0 + nw]
    elif w / h < want / 1.01:
        nh = int(round(w / want)); y0 = (h - nh) // 2; a = a[y0:y0 + nh]
    # Uniform display lift for print legibility (same transform for every layout panel).
    a = (np.clip((a / 255.0) ** gamma * lift, 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(a)
    s = max_px / max(im.size)
    if s < 1:
        im = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.LANCZOS)
    return np.asarray(im), [0, die_um[0], 0, die_um[1]]


def function_map(npz, colors, background=(1, 1, 1), gamma=0.6, floor=0.38, max_px=1100):
    """RGB image of the dominant RTL function per pixel, shaded by occupancy (origin lower-left)."""
    z = np.load(npz)
    dom, occ = z['dominant'], z['occupancy'].astype(float) / 200.0
    rgb = np.ones(dom.shape + (3,)) * np.array(background)
    alpha = np.where(occ > 0, floor + (1 - floor) * np.clip(occ, 0, 1) ** gamma, 0)
    for gi, c in enumerate(colors):
        m = dom == gi
        if not m.any():
            continue
        col = np.array(to_rgb(c))
        rgb[m] = alpha[m, None] * col + (1 - alpha[m, None]) * np.array(background)
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    sc = max_px / max(im.size)
    if sc < 1:
        im = im.resize((int(im.size[0] * sc), int(im.size[1] * sc)), Image.LANCZOS)
    return np.asarray(im), [0, float(z['die_um'][0]), 0, float(z['die_um'][1])]


def group_colors(groups_json, mapping):
    """Colors in the server group order, from a {server group name: color} mapping."""
    g = json.loads(open(groups_json).read())
    return [mapping[n] for n in g['groups']], g


def scalebar(ax, extent, length_um, label, loc='lower right', color='white', pad=0.04):
    x0, x1, y0, y1 = extent
    w, h = x1 - x0, y1 - y0
    if loc == 'lower right':
        xs, ys = x1 - pad * w - length_um, y0 + pad * h
    else:
        xs, ys = x0 + pad * w, y0 + pad * h
    ax.plot([xs, xs + length_um], [ys, ys], color=color, lw=1.6, solid_capstyle='butt')
    ax.text(xs + length_um / 2, ys + 0.012 * h, label, color=color, ha='center', va='bottom', fontsize=6.5)


def frame(ax, extent):
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():     # same hairline frame as the axes of the plotted figures
        s.set_visible(True); s.set_linewidth(fs.LW_AXIS / fs.SCALE); s.set_color(fs.BASE1)
