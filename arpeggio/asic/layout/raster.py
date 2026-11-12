"""Aggregate a private instance table into a functional-map raster (runs on the ASIC server, Python 3.6).

usage: raster.py <insts_private.tsv> <die_public.txt> <rules.json> <out_prefix> [max_px]
Exports only: <out>_raster_public.npz (uint8 dominant-group index, uint8 occupancy) and
<out>_groups_public.json (group names, instance counts, summed cell areas). No instance names,
cell masters or per-instance coordinates are written.
"""
import json, re, sys
import numpy as np

tsv, die_f, rules_f, out = sys.argv[1:5]
max_px = int(sys.argv[5]) if len(sys.argv) > 5 else 1600
die = [float(v) for v in open(die_f).read().split('\n')[0].split()[1:5]]
W_um, H_um = die[2] - die[0], die[3] - die[1]
um_per_px = max(W_um, H_um) / max_px
nx, ny = int(np.ceil(W_um / um_per_px)), int(np.ceil(H_um / um_per_px))
rules = json.load(open(rules_f))
groups = [g for g, _ in rules['rules']] + [rules['default']]
pats = [(i, re.compile(p)) for i, (_, p) in enumerate(rules['rules'])]
strip = re.compile(rules.get('strip', r'^$'))
acc = np.zeros((len(groups), ny, nx), np.float32)
count = np.zeros(len(groups), np.int64); area = np.zeros(len(groups))
skipped = 0
for line in open(tsv):
    n, p, c, b = line.rstrip('\n').split('\t')
    if p == '1':
        skipped += 1; continue
    x0, y0, x1, y1 = [float(v) for v in b.split()[:4]]
    a = (x1 - x0) * (y1 - y0)
    key = ('BLOCK:' if c == 'block' else '') + strip.sub('', n).replace('/', '_')
    gi = len(groups) - 1
    for i, pat in pats:
        if pat.search(key):
            gi = i; break
    count[gi] += 1; area[gi] += a
    i0, i1 = int((x0 - die[0]) / um_per_px), int((x1 - die[0]) / um_per_px)
    j0, j1 = int((y0 - die[1]) / um_per_px), int((y1 - die[1]) / um_per_px)
    i1 = min(max(i1, i0), nx - 1); j1 = min(max(j1, j0), ny - 1)
    npx = (i1 - i0 + 1) * (j1 - j0 + 1)
    acc[gi, j0:j1 + 1, i0:i1 + 1] += a / npx
occ = acc.sum(0) / (um_per_px ** 2)
dom = acc.argmax(0).astype(np.uint8)
dom[occ <= 0] = 255
np.savez_compressed(out + '_raster_public.npz', dominant=dom, occupancy=np.clip(occ * 200, 0, 255).astype(np.uint8),
                    um_per_px=um_per_px, die_um=np.array([W_um, H_um]))
json.dump(dict(groups=groups, count=count.tolist(), area_um2=area.tolist(), physical_only_skipped=skipped,
               die_um=[W_um, H_um], um_per_px=um_per_px, shape=[ny, nx]), open(out + '_groups_public.json', 'w'), indent=1)
print('RASTER_DONE', out, nx, ny)
