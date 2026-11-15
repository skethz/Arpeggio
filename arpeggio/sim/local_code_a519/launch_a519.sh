#!/usr/bin/env bash
# A5.19 launch (run on hostB after the gates pass). Hashes code and inputs into
# results/a519/SHA256SUMS_A519.txt, then starts supervise_a519.sh under setsid/nohup. Refuses if the hash file already exists.
set -euo pipefail
A=<SCRATCH>/arpeggio_ber_20261024
R=$A/results/a519
mkdir -p "$R" "$A/logs/a519"
[ -e "$R/SHA256SUMS_A519.txt" ] && { echo "already launched"; exit 1; }
[ -e "$R/plan.json" ] && { echo "plan exists"; exit 1; }
( cd "$A" && sha256sum src/a519_plan.py src/analyze_a519.py src/sim_a519_plan.py src/supervise_a519.sh src/trace_a514.py src/trace_a56.py \
    src/a56lib.py src/arpx55.py src/arpx514.py src/arpx.py src/a56an.py env_hostb_a519.sh results/a58/select.json \
    results/tuned_a5.json results/tuned_a52.json ) > "$R/SHA256SUMS_A519.txt"
echo "launched $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$R/SHA256SUMS_A519.txt"
setsid nohup bash "$A/src/supervise_a519.sh" >> "$A/logs/a519/supervisor.out" 2>&1 < /dev/null &
sleep 8
cat "$R/SHA256SUMS_A519.txt"; tail -5 "$A/logs/a519/supervisor.log"
