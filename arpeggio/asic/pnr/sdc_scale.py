import re, sys
# Scale a synthesis SDC to a new clock period (ps): period, 5% setup uncertainty and 25% I/O delays (PROTOCOL_ASIC §2).
src, dst, new = sys.argv[1], sys.argv[2], float(sys.argv[3])
t = open(src).read()
old = float(re.search(r'create_clock[^\n]*-period\s+([0-9.]+)', t).group(1))
t = re.sub(r'(create_clock[^\n]*-period\s+)[0-9.]+', lambda m: m.group(1) + '%.1f' % new, t)
t = re.sub(r'(create_clock[^\n]*-waveform\s+\{)\s*[0-9.]+\s+[0-9.]+\s*(\})', lambda m: m.group(1) + '0.0 %.1f' % (new / 2) + m.group(2), t)
t = re.sub(r'(set_clock_uncertainty\s+-setup\s+)[0-9.]+', lambda m: m.group(1) + '%.2f' % (0.05 * new), t)
t = re.sub(r'(set_(?:input|output)_delay\s+-clock\s+\[get_clocks clk\]\s+-add_delay\s+)([0-9.]+)',
           lambda m: m.group(1) + ('%.2f' % (0.25 * new) if abs(float(m.group(2)) - 0.25 * old) < 0.1 else m.group(2)), t)
open(dst, 'w').write(t)
print('period', old, '->', new)
