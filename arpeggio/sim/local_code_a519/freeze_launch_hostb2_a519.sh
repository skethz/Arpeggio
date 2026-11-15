#!/usr/bin/env bash
# A5.19 hostB share (ADDENDUM_A519_HOSTB.md), run on hostB after HZ6 passed and the addendum carries its result and section 7.
# Hashes the new code, the addendum and the gate record into results/a519/SHA256SUMS_A519M.txt (hostB and hostA), copies the addendum
# and gate record next to hostA's protocol files, then starts supervise_hostB2_a519.sh and sync_hostB2_a519.sh under setsid/nohup.
set -euo pipefail
A=<SCRATCH>/ap_ber_20261024
M=$A/a519m
R=$M/results/a519
Z=<SCRATCH>/ap_ber_20261024/a519z
ZS="ssh -n -o BatchMode=yes -o ConnectTimeout=20 <USER>@hostA"
[ -e "$R/SHA256SUMS_A519M.txt" ] && { echo "already frozen"; exit 1; }
$ZS "test ! -e $Z/results/a519/SHA256SUMS_A519M.txt" || { echo "already frozen on hostA"; exit 1; }
grep -q '"pass": true' "$M/results/a519_hz6/gate_HZ6.json" || { echo "HZ6 not passed"; exit 1; }
pgrep -u <USER> -f "supervise_hostB2_a519.sh|sync_hostB2_a519.sh" >/dev/null && { echo "already running"; exit 1; }
mkdir -p "$R" "$M/logs"
cp "$M/ADDENDUM_A519_HOSTB.md" "$R/"; cp "$M/results/a519_hz6/gate_HZ6.json" "$R/"
{
  ( cd "$M" && sha256sum env_hostB2_a519.sh src/supervise_hostB2_a519.sh src/sync_hostB2_a519.sh src/gate_hz6_a519.py \
      results/a519/ADDENDUM_A519_HOSTB.md results/a519/gate_HZ6.json ref/hz6_b00050.npz | sed 's|^\([0-9a-f]*\)  |\1  hostB:a519m/|' )
  ( cd "$A" && sha256sum src/trace_a514.py src/trace_a56.py src/a56lib.py src/apx55.py src/apx514.py src/apx.py src/a56an.py \
      env_hostb_a519.sh results/tuned_a5.json | sed 's|^\([0-9a-f]*\)  |\1  hostB:ap_ber_20261024/|' )
  $ZS "cd $Z && sha256sum src/mz_claims_a519.py src/analyze_a519_hosts.py src/a519_plan.py src/supervise_hosta_a519.sh" | sed 's|^\([0-9a-f]*\)  |\1  hostA:a519z/|'
  echo "frozen on hostB $(date '+%Y-%m-%d %H:%M:%S %Z') (A5.19 hostB share)"
} > "$R/SHA256SUMS_A519M.txt"
rsync -a -e 'ssh -o BatchMode=yes -o ConnectTimeout=20' "$R/SHA256SUMS_A519M.txt" "$R/ADDENDUM_A519_HOSTB.md" "$R/gate_HZ6.json" <USER>@hostA:$Z/results/a519/
setsid nohup bash "$M/src/supervise_hostB2_a519.sh" >> "$M/logs/supervisor.out" 2>&1 < /dev/null &
sleep 5
setsid nohup bash "$M/src/sync_hostB2_a519.sh" >> "$M/logs/sync.out" 2>&1 < /dev/null &
sleep 20
cat "$R/SHA256SUMS_A519M.txt"; tail -5 "$M/logs/supervisor.log"; tail -3 "$M/logs/sync.log"
