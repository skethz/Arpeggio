#!/usr/bin/env bash
# A5.19 on hostA: restart supervise_hosta_a519.sh with NW workers per GPU (argument 1: 0 = paused, the supervisor keeps planning but
# starts no worker; NW <= 2).
# Stops the running supervisor (its workers get SIGTERM through pdeathsig), KILLs any
# worker left after 25 s, checks that none of our pids is on a GPU, renames unreadable done.json, then starts the supervisor again.
# Saved batches stay; each worker's batch in flight is recomputed (stale claims are renamed by the worker's own same-host rule).
NW=${1:?usage: restart_hosta_a519.sh NW}
case "$NW" in 0|1|2) ;; *) echo "NW must be 0, 1 or 2"; exit 1 ;; esac
Z=<SCRATCH>/arpeggio_ber_20261024/a519z
R=$Z/results/a519
L=$Z/logs/a519
PY=<SCRATCH>/mimo_ising_20261016/venv/bin/python
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
sp=$(pgrep -u <USER> -f "bash $Z/src/supervise_hosta_a519.sh")
log "RESTART requested: $NW worker(s) per GPU ($2); stopping supervisor pid(s) ${sp:-none}"
[ -n "$sp" ] && kill -TERM $sp
for t in $(seq 1 25); do pgrep -u <USER> -f "$Z/src/trace_a514.py" >/dev/null || break; sleep 1; done
left=$(pgrep -u <USER> -f "$Z/src/trace_a514.py" | tr '\n' ' ')
[ -n "$left" ] && { kill -KILL $left; sleep 5; }
on=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ' | tr '\n' ' ')
stuck=""; for p in $(cat "$R"/pids/*.pid 2>/dev/null) $left; do case " $on " in *" $p "*) stuck="$stuck $p";; esac; done
for d in $(find "$R" -name done.json); do
  "$PY" -c 'import json, sys; json.load(open(sys.argv[1]))' "$d" 2>/dev/null || { mv "$d" "$d.bad.$(date +%s)"; log "CLEAN unreadable $d"; }
done
rm -f "$R"/pids/*.pid
log "RESTART: old workers gone; KILL needed:${left:- no}; on GPU after:${stuck:- none}"
[ -n "$stuck" ] && { echo "pids still on a GPU:$stuck; not restarting"; exit 1; }
env A519Z_NW=$NW setsid nohup bash "$Z/src/supervise_hosta_a519.sh" >> "$L/supervisor.out" 2>&1 < /dev/null &
sleep 30
tail -n 8 "$L/supervisor.log"
