"""Rewrite the colour operators of the vector figure PDFs; geometry and text stay untouched.

Usage: recolour_figures.py IN_DIR OUT_DIR
A colour with no entry in MAP stops the run, so every source colour is mapped.
"""
import re
import sys
from pathlib import Path

import fitz

FIGS = ['price', 'ber']
BLUE, NAVY, CYAN = '0077C8', '002B49', '00A3E0'
DARK, LIGHT, BLACK, WHITE = '53565A', 'F2F4F7', '000000', 'FFFFFF'
TINT = 'E0EFF8'   # 12% of BLUE on white: flow boxes of our method
MID = 'A0A2A4'    # 55% of DARK on white: second baseline
# Chord #8C1515, first-accept SA #1966FF; source COMP_BLUE is first-accept in Fig. 3. CHORD_TINT is 12% of CHORD on white.
CHORD, CHORD_TINT, ARPEGGIO = '8C1515', 'F1E3E3', '1966FF'
MAP = {
    '76B900': CHORD, '456F00': CHORD, 'E8F1CC': CHORD_TINT,       # ours (Chord)
    'C2410C': NAVY,                                      # sequential SA
    '2A78D6': ARPEGGIO,                                        # first-accept SA (Fig. 3)
    '9C27B0': NAVY,                                      # MDI-AHC
    '5F5F5F': DARK, '57636C': DARK,                      # first baseline, secondary text
    '9AA5B1': MID, 'ABB4BA': MID,                        # second baseline, flow outlines
    'E4E7EB': LIGHT, 'F2F4F5': LIGHT,                    # inactive cells, neutral flow boxes
    '1F2933': BLACK, '202A32': BLACK,                    # ink
    BLACK: BLACK, WHITE: WHITE,
}
NUM = r'(\d*\.?\d+)'
RGB = re.compile(rb'(?<![\w.+\-])' + NUM.encode() + rb'\s+' + NUM.encode() + rb'\s+' + NUM.encode() + rb'\s+(rg|RG)(?!\w)')
GRAY = re.compile(rb'(?<![\w.+\-])' + NUM.encode() + rb'\s+(g|G)(?!\w)')


def to_hex(vals):
    return '%02X%02X%02X' % tuple(round(float(v) * 255) for v in vals)


def to_ops(hex6, stroke, precision):
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    operator = 'RG' if stroke else 'rg'
    return f'{r:.{precision}f} {g:.{precision}f} {b:.{precision}f} {operator}'.encode()


def swap(old, stroke, precision):
    if old not in MAP:
        raise SystemExit(f'unmapped colour #{old}')
    return to_ops(MAP[old], stroke, precision)


def recolour_stream(data, precision=6):
    data, n1 = RGB.subn(lambda m: swap(to_hex(m.group(1, 2, 3)), m.group(4) == b'RG', precision), data)
    data, n2 = GRAY.subn(lambda m: swap(to_hex([m.group(1)] * 3), m.group(2) == b'G', precision), data)
    return data, n1 + n2


def content_xrefs(doc):
    xrefs = set(doc[0].get_contents())
    for x in range(1, doc.xref_length()):
        if doc.xref_is_stream(x) and re.search(r'/Subtype\s*/Form', doc.xref_object(x)):
            xrefs.add(x)
    return xrefs


def main(in_dir, out_dir):
    for name in FIGS:
        src = Path(in_dir) / f'{name}.pdf'
        if not src.exists():
            print(name, 'skipped: no', src)
            continue
        doc = fitz.open(src)
        # Preserve the RGB precision of each published PDF.
        precision = 10 if name == "price" else 6
        total = 0
        for x in content_xrefs(doc):
            new, n = recolour_stream(doc.xref_stream(x), precision)
            total += n
            doc.update_stream(x, new)
        output = Path(out_dir) / f'{name}.pdf'
        doc.save(output, garbage=3, deflate=True)
        doc.close()
        with fitz.open(output) as rendered:
            rendered[0].get_pixmap(dpi=200, alpha=False).save(output.with_suffix('.png'))
        print(name, total, 'colour operators')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
