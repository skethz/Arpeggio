"""Shared style for the regenerated figures of both papers.

8 pt Times New Roman, TrueType (Type 42) fonts, vector PDF with embedded rasters only for layout images,
IEEE text width 7.16 in.

Colour roles follow the author's manuscript colour principle (ckpt/SpinSCI/hardware/manuscript_color.md, 26 Oct 2026):
  OURS (#76B900) marks what we sell: our method, our chosen design point and headline values.
      Text on a green fill is white (OURS_TEXT); OURS_TINT is the table-row tint; OURS_SIDE is only for a 3-D side face.
  BASE1-3 (grays) are baselines; INK is text, GRID the grid.
  COMP_* (blue, orange, purple; alternates and tints) are competitors and other series.
  No other green is used anywhere (no dark green, no teal). Variants within one role differ by marker and line
  style, not by new hues, and every series also carries a marker, a dash pattern or a direct label so that it stays
  distinguishable in grayscale print.
Palette check (dataviz validate_palette, light mode): see the report of 26 Oct 2026. #76B900 is 2.4:1 on white, so
green marks are never thin hairlines and never carry text in green; labels are set in INK beside the green mark.
#2A78D6 and #9C27B0 are the weakest pair under deuteranopia (dE 6.5), so they never differ by colour alone.

Typography and chrome (polish pass, 26 Oct 2026), set at the size each figure prints in the paper:
  one serif family (Times New Roman, STIX math); ticks 7 pt, axis labels and panel titles 8 pt, annotations and
  legends 7 pt. Every figure PDF keeps exactly its pre-polish page size (PRINTED below), so its printed scale and the
  float heights in the papers stay fixed; apply(name) divides the target sizes by that scale.
  Axes 0.5 pt hairlines; reference and target lines 0.5 pt dotted in BASE2 (REF); error bars 0.5 pt, capless, in
  the series colour at reduced opacity (ebar), clipped to the axes.
"""
from pathlib import Path
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
TEXT_W, COL_W = 7.16, 3.5

# --- palette roles -------------------------------------------------------------------------------------------------
OURS = '#76B900'          # ours: method, chosen design point, headline values
OURS_TEXT = '#FFFFFF'     # text on a green fill
OURS_TINT = '#E8F1CC'     # table-row tint (LaTeX: cgreenl)
OURS_SIDE = '#6DAB00'     # 3-D side face of a green solid only
BASE1, BASE2, BASE3 = '#5F5F5F', '#9AA5B1', '#CBD2D9'           # baselines (dark, mid, light gray)
COMP_BLUE, COMP_ORANGE, COMP_PURPLE = '#2A78D6', '#C2410C', '#9C27B0'   # competitors and other series
COMP_BLUE_ALT, COMP_ORANGE_ALT = '#2B6CB0', '#C05621'             # alternates (never beside their main hue)
COMP_BLUE_TINT, COMP_ORANGE_TINT, COMP_PURPLE_TINT = '#CDE2FB', '#FBD9C9', '#EBD4EF'
INK = '#1F2933'           # text, axis labels, primary annotations
GRID = '#E4E7EB'          # grid lines and inactive cells
SURF = '#FFFFFF'          # chart surface
# Text and chrome use the neutrals: INK for primary text, BASE1 for secondary text, ticks and spines,
# BASE2 for reference lines.


def on_fill(color):
    """Text colour on a filled mark: white on the green fill (author's rule), else white or ink by WCAG contrast."""
    if color.upper() == OURS.upper():
        return OURS_TEXT
    r, g, b = (int(color.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return OURS_TEXT if (1.05 / (lum + 0.05)) >= 4.5 else INK


# Printed width in the paper (pt; IEEEtran 10 pt conference: columnwidth 252 pt, textwidth 516 pt) and the
# pre-polish PDF page size (pt). save() writes each of these figures at exactly this page size.
PRINTED = {
    'mechanism': (252.0, 248.104, 184.624), 'price': (516.0, 511.547, 137.24), 'ber': (252.0, 256.29, 137.056),
    'asic_layout_r4': (252.0, 250.56, 160.27), 'fig_ttq': (516.0, 523.214, 164.506),
    'fig_cost': (252.0, 247.379, 218.291),
}
TICK_PT, LABEL_PT, ANNOT_PT = 7.0, 8.0, 7.0      # printed sizes
SCALE = 1.0
TICK, LABEL, ANNOT = TICK_PT, LABEL_PT, ANNOT_PT  # script sizes (set by apply)
LW_AXIS = 0.5             # spines and ticks (printed pt)
REF = dict(color=BASE2, lw=0.5, ls=(0, (1, 2)), dash_capstyle='round', zorder=0.6)   # reference / target lines
EBAR_LW, EBAR_ALPHA = 0.5, 0.45


def ebar(color, alpha=EBAR_ALPHA):
    """Error-bar colour: the series colour itself at reduced opacity (a lighter tint without a new hue)."""
    from matplotlib.colors import to_rgba
    return to_rgba(color, alpha)


def apply(name=None):
    """rcParams for figure `name` (a PRINTED key); sizes are chosen so that they print at the target sizes."""
    global SCALE, TICK, LABEL, ANNOT
    SCALE = PRINTED[name][0] / PRINTED[name][1] if name in PRINTED else 1.0
    TICK, LABEL, ANNOT = TICK_PT / SCALE, LABEL_PT / SCALE, ANNOT_PT / SCALE
    lw = LW_AXIS / SCALE
    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['Times New Roman', 'Times', 'STIXGeneral'],
        'mathtext.fontset': 'stix', 'font.size': LABEL, 'axes.labelsize': LABEL, 'axes.titlesize': LABEL,
        'xtick.labelsize': TICK, 'ytick.labelsize': TICK, 'legend.fontsize': ANNOT,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.linewidth': lw,
        'axes.edgecolor': BASE1, 'axes.labelcolor': INK, 'xtick.color': BASE1, 'ytick.color': BASE1,
        'text.color': INK, 'legend.labelcolor': INK,
        'xtick.major.width': lw, 'ytick.major.width': lw, 'xtick.minor.width': lw * 0.8,
        'ytick.minor.width': lw * 0.8, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
        'xtick.minor.size': 1.5, 'ytick.minor.size': 1.5, 'xtick.major.pad': 2.5, 'ytick.major.pad': 2.5,
        'xtick.direction': 'out', 'ytick.direction': 'out', 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.labelpad': 3.0, 'grid.color': GRID, 'grid.linewidth': 0.4, 'errorbar.capsize': 0,
        'legend.frameon': False, 'axes.titlepad': 4, 'savefig.pad_inches': 0.02, 'image.interpolation': 'antialiased',
    })


def panel_title(ax, letter, text):
    """'(x) ...' at the left end of the axes, same size, colour and pad in every figure."""
    ax.set_title(f'({letter}) {text}', loc='left', fontsize=LABEL, color=INK, pad=4)


def _fixed_bbox(fig, name):
    """Bounding box (inches) of exactly the pre-polish PDF size, centred on the tight bounding box of the content."""
    from matplotlib.transforms import Bbox
    w, h = PRINTED[name][1] / 72.0, PRINTED[name][2] / 72.0
    tb = fig.get_tightbbox(fig.canvas.get_renderer())
    pad = plt.rcParams['savefig.pad_inches']
    if tb.width + 2 * pad > w + 1e-3 or tb.height + 2 * pad > h + 1e-3:
        print(f'WARNING {name}: content {tb.width + 2 * pad:.3f} x {tb.height + 2 * pad:.3f} in exceeds the fixed '
              f'page {w:.3f} x {h:.3f} in')
    cx, cy = 0.5 * (tb.x0 + tb.x1), 0.5 * (tb.y0 + tb.y1)
    return Bbox.from_bounds(cx - w / 2, cy - h / 2, w, h)


def save(fig, paper, name, dpi=600):
    assert paper == 'Antiphase'
    out = ROOT / 'figures'
    out.mkdir(exist_ok=True)
    meta = {'Author': '', 'Creator': '', 'Producer': '', 'Title': name}
    bbox = _fixed_bbox(fig, name) if name in PRINTED else 'tight'
    fig.savefig(out / f'{name}.pdf', metadata=meta, dpi=dpi, bbox_inches=bbox)
    fig.savefig(out / f'{name}.png', dpi=200, bbox_inches=bbox)
    plt.close(fig)
    print('wrote', out / f'{name}.pdf')


def jpeg_compress_pdf(path, quality=92, dpi=450):
    """Re-encode embedded raster images as high-quality JPEG (layout figures only); fonts stay embedded."""
    import subprocess, shutil
    path = Path(path); tmp = path.with_suffix('.tmp.pdf')
    subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.6',
                    '-dAutoFilterColorImages=false', '-dColorImageFilter=/DCTEncode', f'-dJPEGQ={quality}',
                    '-dDownsampleColorImages=true', f'-dColorImageResolution={dpi}', '-dColorImageDownsampleThreshold=1.2',
                    '-dEmbedAllFonts=true', '-dSubsetFonts=true', '-dPreserveAnnots=false',
                    f'-sOutputFile={tmp}', str(path)], check=True)
    shutil.move(tmp, path)
    print('compressed', path, path.stat().st_size)
