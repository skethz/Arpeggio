#!/usr/bin/env bash
# A5.8 operations only (7 Nov 2026 23:3x CET, user: "<instruction>"). Placement within the frozen GPU0-1 only; no code, plan or draw change.
# When one GPU runs >= 2 of our held-out workers and the other runs none, stop (TERM) one of the crowded workers within 20 s of its
# last saved batch. The supervisor then sees its dead claim as startable and relaunches it on the free GPU, where trace_a56 resumes
# from the saved batches (the same path as idle-with-yield). Only our own trace_x64.py workers are signalled. Exits when held-out is done.
A=<SCRATCH>/ap_ber_20261024; R=$A/results/a58; LOG=$A/logs/a58/rebalance.log
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
log "START rebalance pid $$"
while sleep 10; do
  grep -q 'held_done=1' $R/status.txt && { log "held_done=1, exit"; exit 0; }
  declare -A cnt=([g0]=0 [g1]=0); cand=""
  for k in $(seq 0 11); do
    d=$(ls -d $R/held$k/x64/*/snr_22.00 2>/dev/null) || continue
    [ -f $d/done.json ] && continue; [ -f $d/claim.json ] || continue
    w=$(python3 -c "import json;print(json.load(open('$d/claim.json'))['worker'])" 2>/dev/null)
    p=$(python3 -c "import json;print(json.load(open('$d/claim.json'))['pid'])" 2>/dev/null)
    kill -0 "$p" 2>/dev/null || continue
    g=${w:0:2}; cnt[$g]=$((cnt[$g]+1))
    nb=$(ls $d/b*.npz 2>/dev/null | wc -l)
    last=$(ls -t $d/b*.npz 2>/dev/null | head -1); age=$(( $(date +%s) - $(stat -c %Y "$last") ))
    echo "$g $p $w held$k $nb $age"
  done > $A/ops/.rb_state
  for crowd in g0 g1; do
    free=$([ $crowd = g0 ] && echo g1 || echo g0)
    [ ${cnt[$crowd]} -ge 2 ] && [ ${cnt[$free]} -eq 0 ] || continue
    read -r g p w h nb age < <(awk -v g=$crowd '$1==g && $6<20 && $5<=46' $A/ops/.rb_state | head -1)
    [ -n "$p" ] || continue
    if [ "$(ps -o user= -p $p)" = <USER> ] && ps -o args= -p $p | grep -q trace_x64.py; then
      kill -TERM $p && log "TERM $w pid $p ($h, $nb/50 batches, last save ${age}s ago): $crowd has ${cnt[$crowd]}, $free has 0"
      sleep 240
    fi
  done
done
