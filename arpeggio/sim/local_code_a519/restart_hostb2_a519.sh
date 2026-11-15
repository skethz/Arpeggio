#!/usr/bin/env bash
# A5.19 hostB share: restart the sync and the supervisor. Stops the sync first (no new chunks),
# then the supervisor (its workers get SIGTERM through pdeathsig), KILLs any worker left after 25 s, checks that none of our pids is
# on a GPU, renames unreadable done.json, then starts the supervisor and the sync again. Saved batches stay; claims of the stopped
# workers are renamed stale by the worker's own same-host rule; hostB's ownership claims on hostA stay.
A=<SCRATCH>/arpeggio_ber_20261024
M=$A/a519m
R=$M/results/a519
L=$M/logs
PY=$A/venv/bin/python
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L/supervisor.log"; }
log "RESTART requested ($1)"
pkill -TERM -u <USER> -f "bash $M/src/sync_hostB2_a519.sh"
pkill -TERM -u <USER> -f "bash $M/src/supervise_hostB2_a519.sh"
for t in $(seq 1 25); do pgrep -u <USER> -f "worker m[0-3]w" >/dev/null || break; sleep 1; done
left=$(pgrep -u <USER> -f "worker m[0-3]w" | tr '\n' ' ')
[ -n "$left" ] && { kill -KILL $left; sleep 5; }
on=" $(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ' | tr '\n' ' ') "
stuck=""; for p in $(cat "$R"/pids/*.pid 2>/dev/null) $left; do case "$on" in *" $p "*) stuck="$stuck $p";; esac; done
for d in $(find "$R" -name done.json); do
  "$PY" -c 'import json, sys; json.load(open(sys.argv[1]))' "$d" 2>/dev/null || { mv "$d" "$d.bad.$(date +%s)"; log "CLEAN unreadable $d"; }
done
rm -f "$R"/pids/*.pid
log "RESTART: old workers gone; KILL needed:${left:- no}; on GPU after:${stuck:- none}"
[ -n "$stuck" ] && { echo "pids still on a GPU:$stuck; not restarting"; exit 1; }
setsid nohup bash "$M/src/supervise_hostB2_a519.sh" >> "$L/supervisor.out" 2>&1 < /dev/null &
sleep 5
setsid nohup bash "$M/src/sync_hostB2_a519.sh" >> "$L/sync.out" 2>&1 < /dev/null &
sleep 15
tail -n 4 "$L/supervisor.log"; tail -n 2 "$L/sync.log"
