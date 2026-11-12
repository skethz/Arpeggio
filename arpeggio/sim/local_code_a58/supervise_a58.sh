#!/usr/bin/env bash
# A5.8 supervisor (PROTOCOL_A58.md section 9). Untimed BER only. hostB GPU0 and GPU1 only (env_hostb_a56.sh refuses any other UUID).
# Idle-with-yield: a GPU showing any compute process that is not one of our workers gets no new worker, and our workers on it are stopped
# (they resume from saved batches; a stale claim is renamed by trace_a56.claim). Other users' and the author's processes are never touched.
# Every 120 s: rebuild the plan (a58_plan.py), start workers where jobs can start, write status.txt; when the held-out chunks are done, run
# analyze_a58.py once and exit.
A=<SCRATCH>/ap_ber_20261024
R=$A/results/a58
L=$A/logs/a58
PY=$A/venv/bin/python
XF=$A/results/a56/X64F/x64/a56_128_0.3_0.3_0.4_0_alt_8/snr_22.00
W=${A58_WORKERS:-4}
CUT3=1794308400                       # 10 Nov 2026 12:00 CET (section 9, cut 3)
GPUS=(<GPU_UUID> <GPU_UUID>)
mkdir -p "$R/pids" "$L"
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
log "START supervisor pid $$, $W workers per GPU"
while true; do
  read -r NJ NS HD < <(cd "$A" && "$PY" src/a58_plan.py "$R" 2>>"$L/plan.err")
  if [ "$HD" != "1" ] && [ "$(date +%s)" -ge "$CUT3" ]; then
    for f in "$R"/pids/*.pid; do [ -e "$f" ] && kill -TERM "$(cat "$f")" 2>/dev/null; done
    (cd "$A" && "$PY" src/analyze_a58.py "$R" "$XF") >> "$L/analysis.log" 2>&1
    log "TIME CUT (10 Nov 12:00 CET): stopped our workers; analysis on every completed batch, exit $?"
    exit 0
  fi
  if [ "$HD" = "1" ]; then
    (cd "$A" && "$PY" src/analyze_a58.py "$R" "$XF") >> "$L/analysis.log" 2>&1
    log "HELD-OUT DONE; analysis exit $?"
    exit 0
  fi
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader 2>/dev/null | tr -d ' ')
  for gi in 0 1; do
    u=${GPUS[$gi]}
    ours=" "
    for f in "$R"/pids/g${gi}w*.pid; do
      [ -e "$f" ] || continue
      p=$(cat "$f"); if alive "$p"; then ours="$ours$p "; else rm -f "$f"; fi
    done
    foreign=""
    for row in $(echo "$apps" | grep "^$u,"); do
      p=${row#*,}
      case "$ours" in *" $p "*) ;; *) foreign="$foreign $p";; esac
    done
    if [ -n "$foreign" ]; then
      for p in $ours; do kill -TERM "$p" 2>/dev/null; done
      [ "$ours" != " " ] && log "YIELD GPU$gi: foreign pid(s)$foreign; stopped ours:$ours"
      continue
    fi
    n=$(echo $ours | wc -w)
    k=0
    while [ "$n" -lt "$W" ] && [ "${NS:-0}" -gt 0 ]; do
      while [ -e "$R/pids/g${gi}w$k.pid" ]; do k=$((k+1)); done
      ( export MIMO_GPU_UUID=$u; source "$A/env_hostb_a56.sh" >/dev/null && \
        exec nice -n 10 python "$A/src/trace_x64.py" --plan "$R/plan.json" --root "$R" --worker g${gi}w$k --threads 2 --mem 0.20 ) \
        >> "$L/g${gi}w$k.log" 2>&1 &
      echo $! > "$R/pids/g${gi}w$k.pid"
      log "LAUNCH GPU$gi worker g${gi}w$k pid $!"
      n=$((n+1)); NS=$((NS-1))
    done
  done
  {
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') plan_jobs=$NJ startable=$NS held_done=$HD"
    for s in tunea probe tuneb $(seq -f "held%g" 0 11); do
      [ -d "$R/$s" ] && echo "$s done $(find "$R/$s" -name done.json | wc -l) running $(find "$R/$s" -name claim.json | wc -l)"
    done
    echo "workers: $(ls "$R"/pids 2>/dev/null | tr '\n' ' ')"
  } > "$R/status.txt.tmp" && mv "$R/status.txt.tmp" "$R/status.txt"
  sleep 120
done
