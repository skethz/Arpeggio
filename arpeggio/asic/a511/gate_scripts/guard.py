import os, sys, time, signal, subprocess, json
# usage: guard.py <outdir> <timeout_s> <rss_gib> -- cmd...
out, tmo, cap = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]); cmd = sys.argv[sys.argv.index('--')+1:]
p = subprocess.Popen(cmd, start_new_session=True, stdout=open(os.path.join(out,'stdout.log'),'wb'), stderr=subprocess.STDOUT)
t0 = time.time(); peak = 0; why = None
def tree_rss(pgid):
    tot = 0
    for d in os.listdir('/proc'):
        if not d.isdigit(): continue
        try:
            if os.getpgid(int(d)) != pgid: continue
            for line in open('/proc/%s/status' % d):
                if line.startswith('VmRSS:'): tot += int(line.split()[1])
        except Exception: pass
    return tot
while p.poll() is None:
    r = tree_rss(p.pid); peak = max(peak, r)
    if r > cap*1024**2: why = 'rss'
    if time.time()-t0 > tmo: why = 'timeout'
    if why:
        os.killpg(p.pid, signal.SIGTERM); time.sleep(10)
        try: os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        break
    time.sleep(3)
p.wait()
json.dump(dict(exit=p.returncode, killed=why, elapsed=time.time()-t0, peak_rss_gib=peak/1024**2), open(os.path.join(out,'guard_public.json'),'w'))
