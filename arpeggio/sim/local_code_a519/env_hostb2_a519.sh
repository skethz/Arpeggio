#!/usr/bin/env bash
# A5.19 share on hostB GPU0-3 (ADDENDUM_A519_HOSTB.md, amendment 1): held-out chunks only, UNTIMED error counting (no timing/energy).
# Allowed: GPU2, GPU3 (author, 14 Nov 2026: "<instruction>", then "<instruction>"); GPU0, GPU1 from 14 Nov ~13:10
# (author: "<instruction>", then "<instruction>";
# standing allocation GPU0-3). Caller sets MIMO_GPU_UUID;
# then the A5.19 hostB environment (env_hostb_a519.sh: venv, caches in scratch, 2 threads) is sourced.
case "$MIMO_GPU_UUID" in
  <GPU_UUID>|<GPU_UUID>|<GPU_UUID>|<GPU_UUID>) ;;
  *) echo "refusing: MIMO_GPU_UUID=$MIMO_GPU_UUID is not a hostB GPU" >&2; return 1 2>/dev/null || exit 1 ;;
esac
source <SCRATCH>/ap_ber_20261024/env_hostb_a519.sh
