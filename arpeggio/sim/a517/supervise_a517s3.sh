#!/usr/bin/env bash
# A5.17 S3 supervisor (copy of supervise_a514.sh; root, cut, workers, nice/threads changed)
# A5.14-A5.16 supervisor (PROTOCOL_A514/A515/A516 section 10). Untimed BER only. hostB GPU0-3 (env_hostb_a514.sh refuses any other UUID).
# Idle-with-yield, as supervise_a58.sh: a GPU showing any compute process that is not ours gets no new worker, and our float workers on it
# are stopped (they resume from saved batches; trace_a56.claim renames a stale claim). Other users' processes are never touched.
# Workers per GPU: NW (default "4 4 4 3": 15 workers, 2 threads each; with two 4-thread fixed-point processes the total stays <= 24 cores).
# Every 120 s: count startable jobs in the static plan, start workers, write status.txt. Exits when no job is left and no worker runs,
# or at the cut (11 Nov 2026 20:00 CET), when it stops our workers.
A=<SCRATCH>/ap_ber_20261024
R=$A/results/a517s3
L=$A/logs/a517s3
PY=$A/venv/bin/python
read -r -a NW <<< "${A517_NW:-2 2 2 2}"
CUT=$(date -d '2026-11-13 12:00 CET' +%s)
GPUS=(<GPU_UUID> <GPU_UUID> <GPU_UUID> <GPU_UUID>)
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
log "START supervisor pid $$, workers per GPU: ${NW[*]}, cut $(date -d @$CUT)"
while true; do
  read -r NJ NS ND < <(startable)
  if [ -z "$NJ" ]; then log "plan unreadable; waiting"; sleep 120; continue; fi
  if [ "$(date +%s)" -ge "$CUT" ]; then
    for f in "$R"/pids/g*.pid; do [ -e "$f" ] && kill -TERM "$(cat "$f")" 2>/dev/null; done
    log "TIME CUT: stopped our workers; $ND of $NJ jobs done"
    exit 0
  fi
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader 2>/dev/null | tr -d ' ')
  nalive=0
  for gi in 0 1 2 3; do
    u=${GPUS[$gi]}
    ours=" "
    for f in "$R"/pids/g${gi}w*.pid "$R"/pids/x${gi}*.pid; do
      [ -e "$f" ] || continue
      p=$(cat "$f"); if alive "$p"; then ours="$ours$p "; else rm -f "$f"; fi
    done
    for p in $ours; do for c in $(pgrep -P "$p"); do ours="$ours$c "; done; done
    foreign=""
    for row in $(echo "$apps" | grep "^$u,"); do
      p=${row#*,}
      case "$ours" in *" $p "*) ;; *) foreign="$foreign $p";; esac
    done
    if [ -n "$foreign" ]; then
      for f in "$R"/pids/g${gi}w*.pid "$R"/pids/x${gi}*.pid; do
        [ -e "$f" ] || continue
        p=$(cat "$f"); for c in $(pgrep -P "$p"); do kill -TERM "$c" 2>/dev/null; done; kill -TERM "$p" 2>/dev/null
      done
      log "YIELD GPU$gi: foreign pid(s)$foreign; stopped our workers there"
      continue
    fi
    n=0
    for f in "$R"/pids/g${gi}w*.pid; do [ -e "$f" ] && n=$((n+1)); done
    k=0
    while [ "$n" -lt "${NW[$gi]}" ] && [ "${NS:-0}" -gt 0 ]; do
      while [ -e "$R/pids/g${gi}w$k.pid" ]; do k=$((k+1)); done
      ( export MIMO_GPU_UUID=$u; source "$A/env_hostb_a514.sh" >/dev/null && \
        exec taskset -c 0-23 nice -n 19 python "$A/src/trace_a514.py" --plan "$R/plan.json" --root "$R" --worker g${gi}w$k --threads 1 --mem 0.20 ) \
        >> "$L/g${gi}w$k.log" 2>&1 &
      echo $! > "$R/pids/g${gi}w$k.pid"
      log "LAUNCH GPU$gi worker g${gi}w$k pid $!"
      n=$((n+1)); NS=$((NS-1))
      sleep 3
    done
    nalive=$((nalive+n))
  done
  {
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') plan_jobs=$NJ startable=$NS done=$ND workers=$nalive"
    for e in a517; do
      echo "$e done $(ls -d "$R"/${e}_c*/*/*/snr_*/done.json 2>/dev/null | wc -l) running $(ls -d "$R"/${e}_c*/*/*/snr_*/claim.json 2>/dev/null | wc -l)"
    done
  } > "$R/status.txt.tmp" && mv "$R/status.txt.tmp" "$R/status.txt"
  if [ "${NS:-0}" -eq 0 ] && [ "$nalive" -eq 0 ] && [ "$ND" = "$NJ" ]; then log "ALL JOBS DONE"; exit 0; fi
  sleep 120
done
