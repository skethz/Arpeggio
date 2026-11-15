#!/usr/bin/env bash
# A5.19 freeze and launch (run on hostB after the gates pass and section 11 is filled). Hashes code and inputs into
# results/a519/SHA256SUMS_A519.txt, then starts supervise_a519.sh under setsid/nohup. Refuses if the freeze file already exists.
set -euo pipefail
A=<SCRATCH>/ap_ber_20261024
R=$A/results/a519
mkdir -p "$R" "$A/logs/a519"
[ -e "$R/SHA256SUMS_A519.txt" ] && { echo "already frozen"; exit 1; }
[ -e "$R/plan.json" ] && { echo "plan exists before freeze"; exit 1; }
cp "$A/src/PROTOCOL_A519.md" "$R/PROTOCOL_A519.md"
( cd "$A" && sha256sum src/a519_plan.py src/analyze_a519.py src/sim_a519_plan.py src/supervise_a519.sh src/trace_a514.py src/trace_a56.py \
    src/a56lib.py src/apx55.py src/apx514.py src/apx.py src/a56an.py env_hostb_a519.sh results/a519/PROTOCOL_A519.md results/a58/select.json \
    results/tuned_a5.json results/tuned_a52.json ) > "$R/SHA256SUMS_A519.txt"
echo "frozen $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$R/SHA256SUMS_A519.txt"
setsid nohup bash "$A/src/supervise_a519.sh" >> "$A/logs/a519/supervisor.out" 2>&1 < /dev/null &
sleep 8
cat "$R/SHA256SUMS_A519.txt"; tail -5 "$A/logs/a519/supervisor.log"
