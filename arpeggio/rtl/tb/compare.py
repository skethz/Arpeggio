"""Compare the RTL testbench log (rtl_out.txt) with expected.json (gen_vectors.py).
Checks: (1) every command accepted at the model's cycle; (2) output beats identical to the model's, cycle for cycle
(RTL beat cycle = model cycle + 1: outputs are registered); (3) per (tag, anneal) best spins and Δbest equal the
independent reference (anefx for the Philox build, antiphase_ref for the production build).
Usage: compare.py <dir>   -> prints PASS/FAIL lines and a summary; exit 1 on any failure."""
import sys, json, os
d = sys.argv[1]
exp = json.load(open(os.path.join(d, 'expected.json')))
D = exp['D']
acc, beats, end = {}, [], None
for line in open(os.path.join(d, 'rtl_out.txt')):
    t = line.split()
    if not t:
        continue
    if t[0] == 'A':
        acc[int(t[1])] = int(t[2])
    elif t[0] == 'B':
        bits = bin(int(t[5], 16))[2:].zfill(D)
        beats.append([int(t[1]) - 1, int(t[2]), int(t[3]), int(t[4]), bits, int(t[6])])
    elif t[0] == 'E':
        end = int(t[1])
ok_acc = len(acc) == exp['ncmd'] and all(acc.get(i) == c for i, c in enumerate(exp['acc']))
nb = min(len(beats), len(exp['beats']))
first_bad = next((i for i in range(nb) if beats[i] != exp['beats'][i]), None)
ok_beats = len(beats) == len(exp['beats']) and first_bad is None
# reference check
got = {}
for b in beats:
    key = '%d,%d' % (b[1], b[2])
    got.setdefault(key, {})[b[3]] = (b[4], b[5])
nref = nok = 0
for key, (spins, de) in exp['refs'].items():
    nref += 1
    tag = key.split(',')[0]
    P = 2 * exp['tags'][tag][1]
    g = got.get(key, {})
    if len(g) != P:
        continue
    s = ''.join(g[p][0][::-1] for p in range(P))      # beat bits are MSB-first (lane D-1 first) -> lane order
    if s == spins and all(g[p][1] == de for p in range(P)):
        nok += 1
ok_ref = nok == nref
print('%s acceptance cycles: %d/%d commands at the model cycle' % ('PASS' if ok_acc else 'FAIL',
      sum(acc.get(i) == c for i, c in enumerate(exp['acc'])), exp['ncmd']))
print('%s output beats: %d RTL vs %d model, first mismatch %s' % ('PASS' if ok_beats else 'FAIL', len(beats),
      len(exp['beats']), first_bad))
print('%s reference (%s): %d/%d anneals identical (best spins and best energy)' % ('PASS' if ok_ref else 'FAIL',
      exp['ref_kind'], nok, nref))
print('SUMMARY %s D=%d rng=%s rtl_end_cycle=%s model_cycles=%d' % ('PASS' if (ok_acc and ok_beats and ok_ref) else 'FAIL',
      D, exp['rng'], end, exp['cycles']))
sys.exit(0 if (ok_acc and ok_beats and ok_ref) else 1)
