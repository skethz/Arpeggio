"""Aggregated census of instances that fall to the default group (leading name token, digits masked; counts and summed
areas only; no cell masters or coordinates). usage: census_r4.py <insts_private.tsv> <rules.json>"""
import collections, json, re, sys
rules = json.load(open(sys.argv[2])); strip = re.compile(rules.get('strip', r'^$'))
pats = [re.compile(p) for _, p in rules['rules']]
cnt = collections.Counter(); area = collections.Counter(); tot = 0.0
for line in open(sys.argv[1]):
    n, p, c, b = line.rstrip('\n').split('\t')
    if p == '1': continue
    x = [float(v) for v in b.split()[:4]]; a = (x[2] - x[0]) * (x[3] - x[1])
    key = ('BLOCK:' if c == 'block' else '') + strip.sub('', n).replace('/', '_')
    if any(pt.search(key) for pt in pats): continue
    tot += a
    k = re.sub(r'[0-9]+', '#', re.match(r'[A-Za-z_]*[0-9]*[A-Za-z_]*', key).group(0))[:28]
    cnt[k] += 1; area[k] += a
print('unattributed area %.0f' % tot)
for k, v in sorted(area.items(), key=lambda kv: -kv[1])[:25]: print('%-30s n=%7d area=%9.0f %5.1f%%' % (k, cnt[k], v, 100 * v / tot))
