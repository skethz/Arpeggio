#!/usr/bin/env python3
"""A5.14-A5.16 plan (PROTOCOL_A514.md 3, 5; PROTOCOL_A515.md 3, 5; PROTOCOL_A516.md 2). Reads the calibration files, applies the frozen
S rules, writes ROOT/select_a514.json (every calibrated x and the chosen S) and ROOT/plan.json (all held-out chunks, in queue order:
A5.15, A5.16 stage 1, A5.14 P1/P2, A5.14 P4 W = 2, A5.14 P4 W = 4). Refuses if a rule needs a grid extension not yet calibrated.
Usage: plan_a514.py ROOT [--partial]"""
import glob
import json
import os
import sys

ROOT = sys.argv[1]
PARTIAL = '--partial' in sys.argv                                          # before calibration ends: only the S-independent chunks
cal = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'calib_[0-9]*.json'))):
    cal.update(json.load(open(f)))
x = {k: v['x'] for k, v in cal.items()}
PICK = dict(P1='abl_far_64_0.1_0.1_0_rand_32', P2='abl_far_32_0.1_0.1_0_rand_8', P4='abl_far_64_0.1_0.1_0_bal_8')
GRID = dict(P1=range(48, 100, 4), P2=range(24, 60, 4), P4=range(48, 100, 4))


def pick_S(pt, name_of, grid, bound):
    """Largest S on the grid with x <= bound; asks for an extension if the top fits or the bottom does not."""
    xs = {S: x.get('%s/%s' % (pt, name_of(S))) for S in grid}
    if any(v is None for v in xs.values()):
        raise SystemExit('missing calibration: %s %s' % (pt, [S for S, v in xs.items() if v is None]))
    ok = [S for S, v in xs.items() if v <= bound]
    if not ok:
        raise SystemExit('extend grid downward: %s' % pt)
    if max(ok) == max(grid):
        raise SystemExit('extend grid upward: %s' % pt)
    return max(ok), xs


sel = dict(x=x, partial=PARTIAL)
if not PARTIAL:
    # A5.15: S* against re-tuned Chord (C1)
    xc1 = x['P2/abl_ape_0.2_0.2_0.2_rand_8']
    S15, xs15 = pick_S('P2', lambda S: 'abl_far_%d_0.1_0.1_0_rand_8' % S, range(56, 92, 4), xc1)
    sel['A515'] = dict(x_C1=xc1, S_star=S15, x_grid=xs15, method='abl_far_%d_0.1_0.1_0_rand_8' % S15)
    # A5.14: S_W against each pick
    sel['A514'] = {}
    for pt, pk in PICK.items():
        a = pk.split('_')
        tail = '_'.join(a[3:])                                                 # T0_T1_q_start_Ns
        xp = x['%s/%s' % (pt, pk)]
        for W in (2, 4):
            S, xs = pick_S(pt, lambda S, W=W: 'abl_faw_%d_%d_%s' % (W, S, tail), GRID[pt], xp)
            sel['A514']['%s/W%d' % (pt, W)] = dict(x_pick=xp, S=S, x_grid=xs, method='abl_faw_%d_%d_%s' % (W, S, tail))

PT = dict(P1=('x16', 20.0, 102, 2000), P2=('x32', 22.0, 102, 1000), P4=('x64', 22.0, 344, 500))


def chunks(tag, pt, method, b0, b1, size):
    sh, snr, seed, B = PT[pt] if tag != 'a515' else ('x32', 22.0, 2027, 1000)
    out = []
    for c, f in enumerate(range(b0, b1, size)):
        out.append(dict(set='%s_c%03d' % (tag, c), shape=sh, method=method, snr=snr, seed=seed, batch=B, first_batch=f,
                        n_batches=min(size, b1 - f), point=pt, exp=tag))
    return out


def interleave(lists):
    out = []
    for i in range(max(len(l) for l in lists)):
        out += [l[i] for l in lists if i < len(l)]
    return out


jobs = []
astar = [] if PARTIAL else [sel['A515']['method']]
arms15 = ['mdiane8', 'abl_ape_0.2_0.2_0.2_rand_8'] + astar + ['abl_far_32_0.1_0.1_0_rand_8']
jobs += interleave([chunks('a515', 'P2', m, 0, 300, 20) for m in arms15])
jobs += interleave([chunks('a516f', 'P1', PICK['P1'], 14, 200, 6), chunks('a516f', 'P2', PICK['P2'], 43, 300, 10)])
if not PARTIAL:
    jobs += interleave([chunks('a514', 'P1', sel['A514']['P1/W%d' % W]['method'], 0, 200, 6) for W in (2, 4)] +
                       [chunks('a514', 'P2', sel['A514']['P2/W%d' % W]['method'], 0, 300, 10) for W in (2, 4)])
    jobs += chunks('a514', 'P4', sel['A514']['P4/W2']['method'], 0, 600, 4)
    jobs += chunks('a514', 'P4', sel['A514']['P4/W4']['method'], 0, 600, 4)
for fn, obj in (('select_a514.json', sel), ('plan.json', dict(host='hostB', amendment='A5.14-A5.16', jobs=jobs))):
    tmp = os.path.join(ROOT, fn + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, os.path.join(ROOT, fn))
print(len(jobs), 'jobs;', 'partial' if PARTIAL else ('A5.15 S* = %d; A5.14 %s' % (sel['A515']['S_star'], {k: v['S'] for k, v in sel['A514'].items()})))
