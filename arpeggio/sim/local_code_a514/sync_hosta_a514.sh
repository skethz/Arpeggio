#!/usr/bin/env bash
# Pulls finished hostA batches (b*.npz) and done.json of the P4 W = 4 overflow into hostB's results/a514 every 600 s
# (ADDENDUM_A514_HOSTA.md). Claims and temporary files are never copied. Stops after hostA's supervisor exits and a last pull.
A=<SCRATCH>/ap_ber_20261024
Z=<SCRATCH>/ap_ber_20261024/a514z
R=$A/results/a514
L=$A/logs/a514/sync_hosta.log
END=$(date -d '2026-11-11 21:00 CET' +%s)
while true; do
  rsync -a -m --include='a514_c*/' --include='a514_c*/x64/' --include='a514_c*/x64/abl_faw_4_60_0.1_0.1_0_bal_8/' \
        --include='a514_c*/x64/abl_faw_4_60_0.1_0.1_0_bal_8/snr_22.00/' \
        --include='a514_c*/x64/abl_faw_4_60_0.1_0.1_0_bal_8/snr_22.00/b[0-9]*.npz' \
        --include='a514_c*/x64/abl_faw_4_60_0.1_0.1_0_bal_8/snr_22.00/done.json' --exclude='*' \
        -e 'ssh -o BatchMode=yes' <USER>@hostA:$Z/results/a514/ $R/ >> $L 2>&1
  n=$(ls $R/a514_c*/x64/abl_faw_4_60_0.1_0.1_0_bal_8/snr_22.00/b*.npz 2>/dev/null | wc -l)
  zs=$(ssh -n -o BatchMode=yes <USER>@hostA bash $Z/src/zstatus_a514.sh 2>/dev/null | tr '\n' ' ')
  echo "$(date '+%m-%d %H:%M:%S') pulled; P4 W4 batches on hostB: $n; hostA: $zs" >> $L
  case "$zs" in *SUPERVISOR_GONE*) echo "$(date '+%m-%d %H:%M:%S') hostA supervisor gone; last pull done" >> $L; exit 0 ;; esac
  [ "$(date +%s)" -ge "$END" ] && exit 0
  sleep 600
done
