#!/usr/bin/env bash
# A5.19 supervisor (PROTOCOL_A519.md section 10). Untimed BER only. hostB GPU0-3 (standing allocation, 11 Nov; env_hostb_a519.sh refuses
# any other UUID). Shares the GPUs with the author's running jobs (author, 13 Nov: "<instruction>"): no yield, but a memory
# guard that leaves room for the author's next queued job (about 6 GB): no new worker on a GPU with < 9,000 MiB free (one worker takes
# about 3,700 MiB); if a GPU falls below 2,500 MiB free, our newest worker there is stopped (it resumes from saved batches;
# trace_a56.claim renames the stale claim). Other processes are never touched.
# Every 120 s: rebuild the plan (a519_plan.py), start workers, write status.txt. When every held-out chunk is done, or at the time cut
# (section 5), run analyze_a519.py once and exit.
A=<SCRATCH>/ap_ber_20261024
R=$A/results/a519
L=$A/logs/a519
PY=$A/venv/bin/python
read -r -a NW <<< "${A519_NW:-3 3 3 3}"
CUT=$(date -d '2026-11-16 12:00 CET' +%s)
GPUS=(<GPU_UUID> <GPU_UUID> <GPU_UUID> <GPU_UUID>)
mkdir -p "$R/pids" "$L"
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
analyze() { (cd "$A" && "$PY" src/analyze_a519.py "$R" "$R/analysis.json") >> "$L/analysis.log" 2>&1; log "ANALYSIS ($1) exit $?"; }
log "START supervisor pid $$, workers per GPU: ${NW[*]}, cut $(date -d @$CUT)"
while true; do
  read -r NJ NS HD < <(cd "$A" && "$PY" src/a519_plan.py "$R" 2>>"$L/plan.err")
  if [ -z "$NJ" ]; then log "plan failed (plan.err); waiting"; sleep 120; continue; fi
  if [ "$HD" = "1" ]; then
    analyze "held-out done"; exit 0
  fi
  if [ "$(date +%s)" -ge "$CUT" ]; then
    for f in "$R"/pids/g*.pid; do [ -e "$f" ] && kill -TERM "$(cat "$f")" 2>/dev/null; done
    log "TIME CUT (16 Nov 12:00 CET): stopped our workers"
    analyze "time cut"; exit 0
  fi
  nalive=0
  for gi in 0 1 2 3; do
    u=${GPUS[$gi]}
    free=$(nvidia-smi --id="$u" --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')
    [ -z "$free" ] && free=0
    n=0; newest=""
    for f in $(ls -t "$R"/pids/g${gi}w*.pid 2>/dev/null); do
      p=$(cat "$f"); if alive "$p"; then n=$((n+1)); [ -z "$newest" ] && newest=$f; else rm -f "$f"; fi
    done
    if [ "$free" -lt 2500 ] && [ -n "$newest" ]; then
      p=$(cat "$newest"); kill -TERM "$p" 2>/dev/null; rm -f "$newest"; n=$((n-1))
      log "MEMORY GPU$gi: ${free} MiB free; stopped our worker pid $p"
    fi
    k=0
    while [ "$n" -lt "${NW[$gi]}" ] && [ "${NS:-0}" -gt 0 ] && [ "$free" -ge 9000 ]; do
      while [ -e "$R/pids/g${gi}w$k.pid" ]; do k=$((k+1)); done
      ( export MIMO_GPU_UUID=$u; source "$A/env_hostb_a519.sh" >/dev/null && \
        exec nice -n 10 python "$A/src/trace_a514.py" --plan "$R/plan.json" --root "$R" --worker g${gi}w$k --threads 2 --mem 0.20 ) \
        >> "$L/g${gi}w$k.log" 2>&1 &
      echo $! > "$R/pids/g${gi}w$k.pid"
      log "LAUNCH GPU$gi worker g${gi}w$k pid $! (${free} MiB free)"
      n=$((n+1)); NS=$((NS-1)); free=$((free-3700))
      sleep 3
    done
    nalive=$((nalive+n))
  done
  {
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') plan_jobs=$NJ startable=$NS held_done=$HD workers=$nalive"
    for s in tunea tuneb calib; do
      [ -d "$R/$s" ] && echo "$s done $(ls -d "$R"/$s/*/*/snr_*/done.json 2>/dev/null | wc -l) running $(ls -d "$R"/$s/*/*/snr_*/claim.json 2>/dev/null | wc -l)"
    done
    for e in h4 h1; do
      echo "$e chunks done $(ls -d "$R"/${e}_c*/*/*/snr_*/done.json 2>/dev/null | wc -l) running $(ls -d "$R"/${e}_c*/*/*/snr_*/claim.json 2>/dev/null | wc -l)"
    done
  } > "$R/status.txt.tmp" && mv "$R/status.txt.tmp" "$R/status.txt"
  sleep 120
done
