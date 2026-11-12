"""Compare the wrapper's output words (axis_out.txt) with expected.json: identical beats (tag, anneal, copy, bits,
Δbest, in order), and the final word: beats count, no overflow, cycles (model cycles when there were no input gaps).
Usage: compare_axis.py <dir> -> PASS/FAIL lines; exit 1 on failure."""
import sys, os, json
d = sys.argv[1]
exp = json.load(open(os.path.join(d, 'expected.json')))
D = exp['D']
words = [int(l.split()[1], 16) for l in open(os.path.join(d, 'axis_out.txt')) if l.startswith('W ')]
beats, final = [], None
for w in words:
    mk = w >> 248
    if mk == 0x01:
        de = (w >> 32) & ((1 << 36) - 1)
        if de >> 35:
            de -= 1 << 36
        bits = bin((w >> 68) & ((1 << D) - 1))[2:].zfill(D)
        beats.append([w & 0xFFFF, (w >> 16) & 0xFFF, (w >> 28) & 7, bits, de])
    elif mk == 0xFF:
        final = dict(cycles=w & ((1 << 48) - 1), bubbles=(w >> 48) & ((1 << 48) - 1), beats=(w >> 96) & 0xFFFFFFFF, ovf=(w >> 128) & 1)
expb = [[b[1], b[2], b[3], b[4], b[5]] for b in exp['beats']]
ok_b = beats == expb
first = next((i for i in range(min(len(beats), len(expb))) if beats[i] != expb[i]), None)
ok_f = final is not None and final['beats'] == len(expb) and final['ovf'] == 0
print('%s beats: %d vs %d expected, first mismatch %s' % ('PASS' if ok_b else 'FAIL', len(beats), len(expb), first))
print('%s final word: %s (model cycles %d, first acceptance at model cycle %d)' % ('PASS' if ok_f else 'FAIL', final,
      exp['cycles'], exp['acc'][0]))
print('SUMMARY %s' % ('PASS' if ok_b and ok_f else 'FAIL'))
sys.exit(0 if ok_b and ok_f else 1)
