#!/usr/bin/env python3
"""Window a SAIF: given two cumulative SAIF reports of the same simulation (A at t_start, B at t_end, both counted
from time 0, as Questa's 'power report -bsaif' writes them), emit a SAIF for [t_start, t_end]: for every net
T0/T1/TX/TC/IG = B - A and DURATION = t_end - t_start. Nets missing in A are taken from B unchanged.
Usage: saif_window.py A.saif B.saif out.saif
"""
import re
import sys

NUM = re.compile(r'\((T0|T1|TX|TC|IG) (\d+)\)')


class Walker:
    """Tracks the INSTANCE path through the block structure: '(INSTANCE x' and '(NET'/'(PORT' open a block,
    a line holding only ')' closes the innermost block; net entries are single balanced lines."""
    def __init__(self):
        self.blocks = []

    def feed(self, s):
        if s.startswith('(INSTANCE'):
            self.blocks.append(('I', s.split(None, 1)[1].strip()))
        elif s in ('(NET', '(PORT') or s.startswith('(NET ') or s.startswith('(PORT '):
            self.blocks.append(('N', None))
        elif s == ')':
            if self.blocks:
                self.blocks.pop()

    def path(self):
        return '/'.join(n for t, n in self.blocks if t == 'I')


def read_a(path):
    tab, dur, w = {}, None, Walker()
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith('(DURATION'):
                dur = int(s.split()[1].rstrip(')'))
            elif s.startswith('(') and '(T0 ' in s:
                tab[(w.path(), s[1:].split(None, 1)[0])] = {k: int(v) for k, v in NUM.findall(s)}
            else:
                w.feed(s)
    return tab, dur


def main():
    a_path, b_path, out_path = sys.argv[1:4]
    a, dur_a = read_a(a_path)
    w, n_out, n_match, dur_b = Walker(), 0, 0, None
    with open(b_path) as fb, open(out_path, 'w') as fo:
        for line in fb:
            s = line.strip()
            if s.startswith('(DURATION'):
                dur_b = int(s.split()[1].rstrip(')'))
                line = line.replace(str(dur_b), str(dur_b - dur_a))
            elif s.startswith('(') and '(T0 ' in s:
                prev = a.get((w.path(), s[1:].split(None, 1)[0]))
                if prev is not None:
                    n_match += 1
                    line = NUM.sub(lambda m: '(%s %d)' % (m.group(1), int(m.group(2)) - prev.get(m.group(1), 0)), line)
                n_out += 1
            else:
                w.feed(s)
            fo.write(line)
    print('window duration', dur_b - dur_a, 'nets', n_out, 'matched', n_match, 'nets in A', len(a))


if __name__ == '__main__':
    main()
