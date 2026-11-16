#!/usr/bin/env bash
# A5.21 on hostB GPU0-3.
# UNTIMED error counting only. Caller sets MIMO_GPU_UUID; then the A5.19 hostB environment (venv, caches in scratch, 2 threads).
case "$MIMO_GPU_UUID" in
  <GPU_UUID>|<GPU_UUID>|<GPU_UUID>|<GPU_UUID>) ;;
  *) echo "refusing: MIMO_GPU_UUID=$MIMO_GPU_UUID is not a hostB GPU" >&2; return 1 2>/dev/null || exit 1 ;;
esac
source <SCRATCH>/arpeggio_ber_20261024/env_hostb_a519.sh
