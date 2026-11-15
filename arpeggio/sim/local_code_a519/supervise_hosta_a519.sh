#!/usr/bin/env bash
# A5.19 on hostA GPU0, GPU2, GPU3 (ADDENDUM_A519_HOSTA.md). Untimed BER only. Idle-with-yield with five safeguards (addendum section 3):
#  (1) at most 2 workers per GPU, torch memory cap 0.035 of the GPU (6,417 MiB, hostB's absolute cap);
#  (2) a foreign-process check on our GPUs every 15 s;
#  (3) stop = TERM, after 20 s KILL, then an nvidia-smi check that none of our pids is left on that GPU (logged);
#  (4) after every stop, unreadable done.json files are renamed *.bad.<t> (the job rewrites them from its saved batches);
#  (5) workers run under setpriv --pdeathsig TERM, so they stop if this supervisor dies.
# A GPU with any compute process that is not ours gets no new worker until it is free. Other processes are never touched.
# Every 120 s: rebuild the plan (a519_plan.py), start workers, write status.txt. When every held-out chunk is done, or at the time cut
# (PROTOCOL_A519 section 5, 16 Nov 2026 12:00 CET), stop our workers, run analyze_a519.py once and exit.
Z=<SCRATCH>/ap_ber_20261024/a519z
R=$Z/results/a519
L=$Z/logs/a519
PY=<SCRATCH>/mimo_ising_20261016/venv/bin/python
NW=${A519Z_NW:-2}
MEM=0.035
CUT=$(date -d '2026-11-16 12:00 CET' +%s)
GPUS=(<GPU_UUID> <GPU_UUID> <GPU_UUID>)
GN=(0 2 3)
mkdir -p "$R/pids" "$L"
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
ourpids() {                                   # live worker pids on slot $1 (and children), space-delimited; drops dead pid files
  local f p c out=" "
  for f in "$R"/pids/z${GN[$1]}w*.pid; do
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
analyze() { (cd "$Z" && "$PY" src/analyze_a519.py "$R" "$R/analysis.json") >> "$L/analysis.log" 2>&1; log "ANALYSIS ($1) exit $?"; }
log "START supervisor pid $$, workers per GPU: $NW, mem cap $MEM, GPUs ${GN[*]}, cut $(date -d @$CUT)"
declare -a busy=(0 0 0)
it=0
while true; do
  for s in 0 1 2; do                            # (2) every 15 s
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
  if [ $((it % 8)) -eq 0 ]; then                # every 120 s
    read -r NJ NS HD < <(cd "$Z" && "$PY" src/a519_plan.py "$R" 2>>"$L/plan.err")
    if [ -z "$NJ" ]; then
      log "plan failed (plan.err); checking done.json files"; clean_done
    elif [ "$HD" = "1" ]; then
      for s in 0 1 2; do stop_slot "$s" "held-out done"; done
      analyze "held-out done"; exit 0
    elif [ "$(date +%s)" -ge "$CUT" ]; then
      for s in 0 1 2; do stop_slot "$s" "time cut"; done
      log "TIME CUT (16 Nov 12:00 CET): stopped our workers"
      analyze "time cut"; exit 0
    else
      nalive=0
      for s in 0 1 2; do
        u=${GPUS[$s]}; g=${GN[$s]}
        ourpids "$s" > /dev/null                # drops pid files of exited workers
        n=$(ls "$R"/pids/z${g}w*.pid 2>/dev/null | wc -l)
        k=0
        while [ "${busy[$s]}" = 0 ] && [ "$n" -lt "$NW" ] && [ "${NS:-0}" -gt 0 ]; do
          while [ -e "$R/pids/z${g}w$k.pid" ]; do k=$((k+1)); done
          ( export MIMO_GPU_UUID=$u; source "$Z/env_hosta_a519.sh" >/dev/null && \
            exec setpriv --pdeathsig TERM nice -n 10 python "$Z/src/trace_a514.py" --plan "$R/plan.json" --root "$R" --worker z${g}w$k \
              --threads 2 --mem $MEM ) >> "$L/z${g}w$k.log" 2>&1 &
          echo $! > "$R/pids/z${g}w$k.pid"
          log "LAUNCH GPU$g worker z${g}w$k pid $!"
          n=$((n+1)); NS=$((NS-1)); sleep 3
        done
        nalive=$((nalive+n))
      done
      {
        echo "$(date '+%Y-%m-%d %H:%M:%S %Z') plan_jobs=$NJ startable=$NS held_done=$HD workers=$nalive busy=${busy[*]}"
        for st in tunea tuneb calib; do
          [ -d "$R/$st" ] && echo "$st done $(ls -d "$R"/$st/*/*/snr_*/done.json 2>/dev/null | wc -l)"
        done
        for e in h4 h1; do echo "$e chunks done $(ls -d "$R"/${e}_c*/*/*/snr_*/done.json 2>/dev/null | wc -l)"; done
      } > "$R/status.txt.tmp" && mv "$R/status.txt.tmp" "$R/status.txt"
    fi
  fi
  it=$((it+1)); sleep 15
done
