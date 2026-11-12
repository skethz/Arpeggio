#!/usr/bin/env bash
# A5.13 finisher (PROTOCOL_A513.md section 3): every 5 min, count completed batches; when every run is complete, or at the time cut
# (10 Nov 2026 12:00 CET), run analyze_a513.py once on every completed batch and stop.
source <SCRATCH>/ap_ber_20261024/env_ap.sh > /dev/null 2>&1
export OMP_NUM_THREADS=2
cd <SCRATCH>/ap_ber_20261024/a513
CUT=$(date -d '2026-11-10 12:00 CET' +%s)
n() { ls "$1" 2>/dev/null | grep -c '^b.*npz$'; }
while true; do
  a=$(n results/x16/fafx_64_0.1_0.1_0_rand_32/snr_20.00); b=$(n results/x32/fafx_32_0.1_0.1_0_rand_8/snr_22.00)
  c=$(n results/x64/fafx_64_0.1_0.1_0_bal_8/snr_22.00)
  h=$(( $(n hostcheck/x16/prod_fx_xs_32/snr_20.00) + $(n hostcheck/x32/prod_fx_xs_8/snr_22.00) + $(n hostcheck/x64/prod_fx_xs_8/snr_22.00) ))
  echo "$(date '+%m-%d %H:%M:%S') P1 $a/200 P2 $b/300 P4 $c/600 host $h/87" >> logs/finish.log
  if [ "$a" -ge 200 ] && [ "$b" -ge 300 ] && [ "$c" -ge 600 ] && [ "$h" -ge 87 ]; then out=results/analysis.json; break; fi
  if [ "$(date +%s)" -ge "$CUT" ]; then out=results/analysis_timecut.json; break; fi
  sleep 300
done
nice -n 10 python src/analyze_a513.py results refs/refs_a513.npz $out hostcheck >> logs/finish.log 2>&1
sha256sum $out >> logs/finish.log
echo "ANALYSIS DONE $out" >> logs/finish.log
