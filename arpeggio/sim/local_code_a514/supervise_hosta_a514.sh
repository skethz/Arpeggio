#!/usr/bin/env bash
# A5.14 P4 W = 4 overflow on hostA GPU5 (ADDENDUM_A514_HOSTA.md). Untimed BER only. Idle-with-yield as supervise_a514.sh: if GPU5 shows
# any compute process that is not ours, our workers there are stopped (they resume from saved batches) and none is started.
# Other users' processes are never touched. Workers: NW (default 6), 2 threads each. Every 120 s; exits when no job is left and no
# worker runs, or at the cut (11 Nov 2026 20:00 CET).
Z=<SCRATCH>/ap_ber_20261024/a514z
R=$Z/results/a514
L=$Z/logs/a514
PY=<SCRATCH>/mimo_ising_20261016/venv/bin/python
NW=${A514Z_NW:-6}
U=<GPU_UUID>
CUT=$(date -d '2026-11-11 20:00 CET' +%s)
mkdir -p "$R/pids" "$L"
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
startable() { "$PY" - "$R" <<'PYX'
import json, os, sys
R = sys.argv[1]
n = t = d = 0
for j in json.load(open(os.path.join(R, 'plan.json')))['jobs']:
    t += 1
    jd = os.path.join(R, j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    if os.path.exists(os.path.join(jd, 'done.json')):
        d += 1; continue
    if os.path.isdir(jd) and sum(f.startswith('failed.') for f in os.listdir(jd)) >= 3:
        continue
    cl = os.path.join(jd, 'claim.json')
    if os.path.exists(cl):
        try:
            if os.path.exists('/proc/%d' % int(json.load(open(cl))['pid'])):
                continue
        except Exception:
            continue
    n += 1
print(t, n, d)
PYX
}
log "START supervisor pid $$, workers: $NW, cut $(date -d @$CUT)"
while true; do
  read -r NJ NS ND < <(startable)
  if [ -z "$NJ" ]; then log "plan unreadable; waiting"; sleep 120; continue; fi
  if [ "$(date +%s)" -ge "$CUT" ]; then
    for f in "$R"/pids/g5w*.pid; do [ -e "$f" ] && kill -TERM "$(cat "$f")" 2>/dev/null; done
    log "TIME CUT: stopped our workers; $ND of $NJ jobs done"; exit 0
  fi
  ours=" "
  for f in "$R"/pids/g5w*.pid; do
    [ -e "$f" ] || continue
    p=$(cat "$f"); if alive "$p"; then ours="$ours$p "; else rm -f "$f"; fi
  done
  for p in $ours; do for c in $(pgrep -P "$p"); do ours="$ours$c "; done; done
  foreign=""
  for row in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader 2>/dev/null | tr -d ' ' | grep "^$U,"); do
    p=${row#*,}; case "$ours" in *" $p "*) ;; *) foreign="$foreign $p";; esac
  done
  n=0
  if [ -n "$foreign" ]; then
    for f in "$R"/pids/g5w*.pid; do
      [ -e "$f" ] || continue
      p=$(cat "$f"); for c in $(pgrep -P "$p"); do kill -TERM "$c" 2>/dev/null; done; kill -TERM "$p" 2>/dev/null
    done
    log "YIELD GPU5: foreign pid(s)$foreign; stopped our workers"
  else
    for f in "$R"/pids/g5w*.pid; do [ -e "$f" ] && n=$((n+1)); done
    k=0
    while [ "$n" -lt "$NW" ] && [ "${NS:-0}" -gt 0 ]; do
      while [ -e "$R/pids/g5w$k.pid" ]; do k=$((k+1)); done
      ( source "$Z/env_hosta_a514.sh" >/dev/null && \
        exec nice -n 10 python "$Z/src/trace_a514.py" --plan "$R/plan.json" --root "$R" --worker g5w$k --threads 2 --mem 0.12 ) \
        >> "$L/g5w$k.log" 2>&1 &
      echo $! > "$R/pids/g5w$k.pid"
      log "LAUNCH GPU5 worker g5w$k pid $!"
      n=$((n+1)); NS=$((NS-1)); sleep 3
    done
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') plan_jobs=$NJ startable=$NS done=$ND workers=$n" > "$R/status.txt.tmp" && mv "$R/status.txt.tmp" "$R/status.txt"
  if [ "${NS:-0}" -eq 0 ] && [ "$n" -eq 0 ] && [ "$ND" = "$NJ" ]; then log "ALL JOBS DONE"; exit 0; fi
  sleep 120
done
