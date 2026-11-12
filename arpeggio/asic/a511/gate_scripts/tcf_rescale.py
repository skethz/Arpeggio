#!/usr/bin/env python3
"""Time-rescale a Genus netlist TCF by K: only the header duration token changes (duration_new = K x duration_old);
every toggle count and duty is byte-identical (PROTOCOL.md 2). Python 3.6. usage: tcf_rescale.py in.tcf out.tcf K"""
import re, sys, hashlib
src, dst, k = sys.argv[1], sys.argv[2], float(sys.argv[3])
data = open(src, 'rb').read()
head = data[:4096].decode('ascii', 'replace')
pat = re.compile(r'duration\s*:\s*"([0-9.eE+-]+)"\s*;')
ms = list(pat.finditer(head))
assert len(ms) == 1, 'expected exactly one duration token in the header'
assert len(pat.findall(data.decode('ascii', 'replace'))) == 1, 'duration token not unique in file'
old = float(ms[0].group(1)); new = old * k
tok = ('%.6e' % new)
s, e = ms[0].span(1)
out = data[:s] + tok.encode() + data[e:]
open(dst, 'wb').write(out)
a = data.split(b'\n'); b = out.split(b'\n')
ndiff = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
print('rescale K=%g duration %g -> %s ; lines differing: %d ; sha256 in %s out %s' % (
    k, old, tok, ndiff, hashlib.sha256(data).hexdigest()[:16], hashlib.sha256(out).hexdigest()[:16]))
assert ndiff == 1
