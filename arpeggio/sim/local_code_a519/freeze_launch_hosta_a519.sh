#!/usr/bin/env bash
# A5.19 on hostA (ADDENDUM_A519_HOSTA.md): run after host gate HZ passed and the addendum carries its result. Hashes code, inputs,
# the addendum and the gate record into results/a519/SHA256SUMS_A519Z.txt, then starts supervise_hosta_a519.sh under setsid/nohup.
set -euo pipefail
Z=<SCRATCH>/ap_ber_20261024/a519z
R=$Z/results/a519
[ -e "$R/SHA256SUMS_A519Z.txt" ] && { echo "already frozen on hostA"; exit 1; }
grep -q '"pass": true' "$Z/results/a519_hz/gate_HZ.json" || { echo "host gate not passed"; exit 1; }
pgrep -u <USER> -f "supervise_hosta_a519.sh" >/dev/null && { echo "supervisor already running"; exit 1; }
cp "$Z/ADDENDUM_A519_HOSTA.md" "$R/ADDENDUM_A519_HOSTA.md"
cp "$Z/results/a519_hz/gate_HZ.json" "$R/gate_HZ.json"
( cd "$Z" && sha256sum src/a519_plan.py src/analyze_a519.py src/supervise_hosta_a519.sh src/gate_hz_a519.py src/trace_a514.py src/trace_a56.py \
    src/a56lib.py src/apx55.py src/apx514.py src/apx.py src/a56an.py env_hosta_a519.sh results/a519/ADDENDUM_A519_HOSTA.md \
    results/a519/PROTOCOL_A519.md results/a519/SHA256SUMS_A519.txt results/a519/gate_HZ.json results/a58/select.json results/tuned_a52.json \
    <SCRATCH>/ap_ber_20261024/results/tuned_a5.json ) > "$R/SHA256SUMS_A519Z.txt"
echo "frozen on hostA $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$R/SHA256SUMS_A519Z.txt"
setsid nohup bash "$Z/src/supervise_hosta_a519.sh" >> "$Z/logs/a519/supervisor.out" 2>&1 < /dev/null &
sleep 25
cat "$R/SHA256SUMS_A519Z.txt"; tail -8 "$Z/logs/a519/supervisor.log"
