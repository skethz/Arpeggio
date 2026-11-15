#!/usr/bin/env bash
# A5.19 share with hostB, runs on hostB every 120 s:
#  (1) push: hostB's held-out and calibration batch files (b*.npz, written atomically) into hostA's results/a519,
#      then the done.json of chunks finished more than a minute ago. A file hostA already has is never overwritten; claims and
#      temporary files are never copied.
#  (2) take: hostB keeps up to (GPUs not yielding) + BUF chunks open (BUF 2 waiting chunks so a worker never idles
#      between chunks); hostA hands over the missing number from the end of its plan
#      (mz_claims_a519.py take N KEEP; at least KEEP chunks stay for hostA's own workers); they are added to hostB's plan.json.
# Calibration jobs go first in hostB's plan; KEEP is read from a519m/keep.txt each cycle (0 while hostA is paused).
# Exits after a last push when hostA's supervisor has exited (analysis done) or at 11:58 CET.
A=<SCRATCH>/arpeggio_ber_20261024
M=$A/a519m
R=$M/results/a519
L=$M/logs/sync.log
Z=<SCRATCH>/arpeggio_ber_20261024/a519z
PY=$A/venv/bin/python
BUF=2
KEEP0=3
END=$(date -d '2026-11-16 11:58 CET' +%s)
STOPTAKE=$(date -d '2026-11-16 11:50 CET' +%s)
RSH='ssh -o BatchMode=yes -o ConnectTimeout=20'
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$L"; }
push() {
  ( cd "$R" && find . \( -path './h[14]_c*' -o -path './calib/*' \) -name 'b[0-9]*.npz' -printf '%P\n' | sort ) > "$M/push_b.txt"
  ( cd "$R" && find . \( -path './h[14]_c*' -o -path './calib/*' \) -name done.json -mmin +1 -printf '%P\n' | sort ) > "$M/push_d.txt"
  rsync -a --ignore-existing --files-from="$M/push_b.txt" -e "$RSH" "$R/" <USER>@hostA:$Z/results/a519/ >> "$L" 2>&1 && \
    rsync -a --ignore-existing --files-from="$M/push_d.txt" -e "$RSH" "$R/" <USER>@hostA:$Z/results/a519/ >> "$L" 2>&1
}
nopen() {                                     # hostB plan jobs without done.json (running or waiting)
  "$PY" - "$R" <<'P'
import json, os, sys
R = sys.argv[1]
try:
    jobs = json.load(open(os.path.join(R, 'plan.json')))['jobs']
except Exception:
    jobs = []
print(sum(not os.path.exists(os.path.join(R, j['set'], j['shape'], j['method'], 'snr_%05.2f' % float(j['snr']), 'done.json'))
          for j in jobs))
P
}
merge() {                                     # stdin: JSON lines from mz_claims take; appended to hostB's plan.json (atomic)
  "$PY" -c '
import json, os, sys
R = sys.argv[1]; p = os.path.join(R, "plan.json")
try:
    plan = json.load(open(p))
except Exception:
    plan = dict(host="hostB", experiment="A5.19 share", jobs=[])
have = {(j["set"], j["method"]) for j in plan["jobs"]}
new = [json.loads(l) for l in sys.stdin if l.strip()]
plan["jobs"] += [j for j in new if (j["set"], j["method"]) not in have]
plan["jobs"].sort(key=lambda j: j["set"] != "calib")   # calibration first (stable)
json.dump(plan, open(p + ".tmp", "w"), indent=1); os.replace(p + ".tmp", p)
print(len(new))' "$R"
}
mkdir -p "$R" "$(dirname "$L")"
log "START sync pid $$, open up to free GPUs + $BUF, keep from keep.txt (default $KEEP0) for hostA"
while true; do
  push; pr=$?
  took=0
  KEEP=$(cat "$M/keep.txt" 2>/dev/null | tr -cd 0-9); KEEP=${KEEP:-$KEEP0}
  op=$(nopen); ng=$(tr ' ' '\n' < "$R/busy.txt" 2>/dev/null | grep -c '^0$'); cap=0; [ "$ng" -gt 0 ] && cap=$((ng + BUF)); free=$((cap - op))
  [ "$free" -lt 0 ] && free=0                 # take is called every cycle; with 0 it hands over calibration jobs only
  if [ "$(date +%s)" -lt "$STOPTAKE" ]; then
    got=$(ssh -n -o BatchMode=yes -o ConnectTimeout=20 <USER>@hostA "python3 $Z/src/mz_claims_a519.py take $free $KEEP" 2>> "$L")
    [ -n "$got" ] && took=$(echo "$got" | merge)
  fi
  zs=$(ssh -n -o BatchMode=yes -o ConnectTimeout=20 <USER>@hostA "pgrep -u <USER> -f supervise_hosta_a519.sh >/dev/null && echo up || echo gone" 2>/dev/null)
  log "push exit $pr; batches here $(wc -l < "$M/push_b.txt"), done chunks $(wc -l < "$M/push_d.txt"); open $op, took $took, keep $KEEP; hostA supervisor ${zs:-unreachable}"
  if [ "$zs" = "gone" ]; then push; log "hostA supervisor gone; last push exit $?; exiting"; exit 0; fi
  if [ "$(date +%s)" -ge "$END" ]; then push; log "11:58 CET: last push exit $?; exiting"; exit 0; fi
  sleep 120
done
