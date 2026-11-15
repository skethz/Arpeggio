#!/usr/bin/env python3
"""Prints the S-rule outputs from results/a514/select_a514.json as markdown."""
import json, sys
s = json.load(open(sys.argv[1]))
x = s['x']
out = []
a = s['A515']
out.append('### A5.15 (S rule)')
out.append('- x(C1) = %.4f (`abl_chord_0.2_0.2_0.2_rand_8`); x(A32) = %.4f.' % (a['x_C1'], x['P2/abl_far_32_0.1_0.1_0_rand_8']))
out.append('- Grid x(S): ' + ', '.join('%s: %.4f' % (S, v) for S, v in sorted(a['x_grid'].items(), key=lambda t: int(t[0]))) + '.')
out.append('- **S* = %d** (`%s`).' % (a['S_star'], a['method']))
out.append('')
out.append('### A5.14 (S rule)')
for k, v in s['A514'].items():
    out.append('- %s: x(pick) = %.4f; grid ' % (k, v['x_pick']) + ', '.join('%s: %.4f' % (S, xv) for S, xv in sorted(v['x_grid'].items(), key=lambda t: int(t[0]))) + '; **S = %d** (`%s`).' % (v['S'], v['method']))
print('\n'.join(out))
