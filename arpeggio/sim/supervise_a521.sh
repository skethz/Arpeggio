#!/usr/bin/env bash
# A5.21 on hostB GPU0-3.
# Untimed BER only. Waits until A5.20's supervisor has exited (its yield check would treat our workers as foreign), then runs with the
# five yield safeguards of supervise_a520.sh:
#  (1) 1 worker per GPU, memory cap 0.20 of the GPU;
#  (2) a foreign-process check on our GPUs every 15 s;
#  (3) stop = TERM, after 20 s KILL, then an nvidia-smi check that none of our pids is left on that GPU (logged);
#  (4) after every stop, unreadable done.json files are renamed *.bad.<t> (the job rewrites them from its saved batches);
#  (5) workers run under setpriv --pdeathsig TERM, so they stop if this supervisor dies.
# A GPU with any compute process that is not ours gets no new worker until it is free. Other processes are never touched.
# Every 120 s: a521_plan.py (writes plan.json, select.json), start workers if a job is startable, write status.txt.
# A gate that failed three times: stop, no analysis, exit. When select.json says held_done and no worker is alive: analyze_a521.py once,
# then exit. At the time cut: stop our workers, run the analysis on the completed batches, exit.
A=<SCRATCH>/arpeggio_ber_20261024
M=$A/a521
R=$M/results/a521
L=$M/logs
PY=$A/venv/bin/python
NW=1
MEM=0.20
CUT=$(date -d '2026-11-17 18:00 CET' +%s)
GPUS=(<GPU_UUID> <GPU_UUID> <GPU_UUID> <GPU_UUID>)
GN=(0 1 2 3)
mkdir -p "$R/pids" "$L"
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
ourpids() {                                   # live worker pids on slot $1 (and children), space-delimited; drops dead pid files
  local f p c out=" "
  for f in "$R"/pids/a${GN[$1]}w*.pid; do
    [ -e "$f" ] || continue
    p=$(cat "$f")
    if alive "$p"; then out="$out$p "; for c in $(pgrep -P "$p"); do out="$out$c "; done; else rm -f "$f"; fi
  done
  echo "$out"
}
gpupids() { nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader 2>/dev/null | tr -d ' ' | awk -F, -v u="$1" '$1==u{print $2}'; }
clean_done() {
  local d
  for d in $(find "$R" -name done.json); do
    "$PY" -c 'import json, sys; json.load(open(sys.argv[1]))' "$d" 2>/dev/null || { mv "$d" "$d.bad.$(date +%s)"; log "CLEAN unreadable $d"; }
  done
}
stop_slot() {                                 # $1 slot, $2 reason
  local s=$1 before p t left on stuck=""
  before=$(ourpids "$s")
  [ "$before" = " " ] && return
  for p in $before; do kill -TERM "$p" 2>/dev/null; done
  for t in $(seq 1 20); do left=$(ourpids "$s"); [ "$left" = " " ] && break; sleep 1; done
  left=$(ourpids "$s")
  if [ "$left" != " " ]; then for p in $left; do kill -KILL "$p" 2>/dev/null; done; sleep 5; fi
  on=" $(gpupids "${GPUS[$s]}" | tr '\n' ' ') "
  for p in $before; do case "$on" in *" $p "*) stuck="$stuck $p";; esac; done
  clean_done
  log "STOP GPU${GN[$s]} ($2): pids$before; KILL needed:$([ "$left" != " " ] && echo "$left" || echo ' no'); on GPU after:${stuck:- none}"
}
startable() {                                 # plan jobs with no done.json and no live claim
  "$PY" - "$R" <<'P'
import json, os, sys
R = sys.argv[1]
try:
    jobs = json.load(open(os.path.join(R, 'plan.json')))['jobs']
except Exception:
    print(0); sys.exit()
n = 0
for j in jobs:
    d = os.path.join(R, j['set'], j['shape'], j['method'], 'snr_%05.2f' % float(j['snr']))
    if os.path.exists(os.path.join(d, 'done.json')):
        continue
    cl = os.path.join(d, 'claim.json')
    if not os.path.exists(cl):
        n += 1
        continue
    try:
        n += not os.path.exists('/proc/%d' % int(json.load(open(cl))['pid']))
    except Exception:
        pass
print(n)
P
}
analyze() {                                   # $1 reason; runs once
  [ -e "$R/analysis.json" ] && return
  log "ANALYSIS ($1)"
  ( cd "$A/src" && PYTHONPATH="$A/src" "$PY" "$M/src/analyze_a521.py" "$R" "$R/analysis.json" ) >> "$L/analysis.log" 2>&1
  log "ANALYSIS exit $?"
}
nlive() { local s n=0; for s in 0 1 2 3; do [ "$(ourpids "$s")" != " " ] && n=$((n+1)); done; echo $n; }
log "START supervisor pid $$, workers per GPU: $NW, mem cap $MEM, GPUs ${GN[*]}, cut $(date -d @$CUT)"
w=0
while pgrep -f 'a520/src/supervise_a520.sh' > /dev/null || pgrep -f 'a520/results/a520/plan.json' > /dev/null; do
  [ "$w" = 0 ] && log "WAIT: A5.20 supervisor or workers still running"
  w=1; sleep 60
  if [ "$(date +%s)" -ge "$CUT" ]; then log "TIME CUT reached while waiting for A5.20; no job ran"; exit 0; fi
done
log "A5.20 gone; starting"
declare -a busy=(0 0 0 0)
it=0
while true; do
  for s in 0 1 2 3; do                          # (2) every 15 s
    ours=$(ourpids "$s"); foreign=""
    for p in $(gpupids "${GPUS[$s]}"); do case "$ours" in *" $p "*) ;; *) foreign="$foreign $p";; esac; done
    if [ -n "$foreign" ]; then
      [ "${busy[$s]}" = 0 ] && log "FOREIGN GPU${GN[$s]}: pid(s)$foreign"
      busy[$s]=1
      [ "$ours" != " " ] && stop_slot "$s" "yield to$foreign"
    else
      [ "${busy[$s]}" = 1 ] && log "FREE GPU${GN[$s]} again"
      busy[$s]=0
    fi
  done
  if [ "$(date +%s)" -ge "$CUT" ]; then
    for s in 0 1 2 3; do stop_slot "$s" "time cut"; done
    ( cd "$A/src" && "$PY" "$M/src/a521_plan.py" "$R" ) >> "$L/plan.log" 2>&1
    analyze "time cut 17 Nov 18:00 CET"
    log "EXIT after the time cut"
    exit 0
  fi
  if [ $((it % 8)) -eq 0 ]; then                # every 120 s
    ( cd "$A/src" && "$PY" "$M/src/a521_plan.py" "$R" ) >> "$L/plan.log" 2>&1 || log "PLANNER exit $?"
    if "$PY" -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1])).get("stop") else 1)' "$R/select.json" 2>/dev/null; then
      for s in 0 1 2 3; do stop_slot "$s" "gate failed"; done
      log "STOP: a gate failed three times (select.json gate_failed); no analysis"
      exit 1
    fi
    if "$PY" -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1])).get("held_done") else 1)' "$R/select.json" 2>/dev/null \
       && [ "$(nlive)" = 0 ]; then
      analyze "all held-out batches done"
      log "EXIT after the analysis"
      exit 0
    fi
    NS=$(startable)
    nalive=0
    for s in 0 1 2 3; do
      u=${GPUS[$s]}; g=${GN[$s]}
      ourpids "$s" > /dev/null                  # drops pid files of exited workers
      n=$(ls "$R"/pids/a${g}w*.pid 2>/dev/null | wc -l)
      k=0
      while [ "${busy[$s]}" = 0 ] && [ "$n" -lt "$NW" ] && [ "${NS:-0}" -gt 0 ]; do
        while [ -e "$R/pids/a${g}w$k.pid" ]; do k=$((k+1)); done
        ( export MIMO_GPU_UUID=$u; source "$M/env_a521.sh" >/dev/null && \
          exec setpriv --pdeathsig TERM nice -n 10 python "$A/src/trace_a514.py" --plan "$R/plan.json" --root "$R" --worker a${g}w$k \
            --threads 2 --mem $MEM ) >> "$L/a${g}w$k.log" 2>&1 &
        echo $! > "$R/pids/a${g}w$k.pid"
        log "LAUNCH GPU$g worker a${g}w$k pid $!"
        n=$((n+1)); NS=$((NS-1)); sleep 3
      done
      nalive=$((nalive+n))
    done
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') startable=$(startable) workers=$nalive busy=${busy[*]}" > "$R/status.txt.tmp" && \
      mv "$R/status.txt.tmp" "$R/status.txt"
  fi
  it=$((it+1)); sleep 15
done
