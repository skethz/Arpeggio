#!/usr/bin/env bash
# A5.12 supervisor (PROTOCOL_A512.md section 6), run with nohup on hostA. GPU7 only; 2 workers, each started with --max-jobs 1
# and relaunched, so every start re-reads tuned_a512.json (no restart after a pick). Idle-with-yield: any compute process on
# GPU7 that is not ours stops our workers; they resume when it is gone. Our runner CPU <= 12 cores. Stops on a job with
# >= 3 failed attempts. 24 h wall-clock cap. When every job is done: analyze_a512.py, then A512_DONE.
B=<SCRATCH>/ap_ber_20261024/a512
U=<GPU_UUID>
PL=$B/results/plan_a512.json
LOG=$B/logs/supervisor_a512.log
REF=<SCRATCH_MOUNT>/ap_ber_20261024/results
source $B/env_a512.sh
T0=$(date +%s)
foreign() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $U | awk -F', ' '{print $2}'); do
              tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q plan_a512.json || echo $p; done | wc -l; }
ourcpu() { ps -eo pcpu,args | grep "plan_a512.json" | grep -v grep | awk '{s+=$1} END{print int(s)}'; }
running() { pgrep -f "runner.py --plan $PL --root $B/results --worker $1( |$)" > /dev/null; }
echo "$(date '+%F %T') A5.12 supervisor start (pid $$)" >> $LOG
while true; do
  if [ "$(foreign)" -gt 0 ]; then
    pkill -f "runner.py --plan $PL" && echo "$(date '+%F %T') foreign compute process on GPU7: our workers stopped (yield)" >> $LOG
    sleep 120; continue
  fi
  python src/select_a512.py $B/results >> $LOG 2>&1
  [ $? -eq 10 ] && echo "$(date '+%F %T') pick written" >> $LOG
  st=$(python src/status_a512.py $PL $B/results); left=$(echo $st | awk '{print $2}'); fmax=$(echo $st | awk '{print $4}')
  if [ "$fmax" -ge 3 ]; then echo "$(date '+%F %T') a job failed 3 times; stopping" >> $LOG; pkill -f "runner.py --plan $PL"; break; fi
  if [ "$left" -eq 0 ]; then
    if python src/analyze_a512.py $B/results $REF > $B/results/a512_analysis.txt 2>> $LOG; then
      echo "$(date '+%F %T') A5.12 complete" >> $LOG; else echo "$(date '+%F %T') analysis failed" >> $LOG; fi
    date '+%F %T' > $B/results/A512_DONE; break
  fi
  if [ $(( $(date +%s) - T0 )) -gt 86400 ]; then echo "$(date '+%F %T') 24 h cap" >> $LOG; pkill -f "runner.py --plan $PL"; break; fi
  if [ "$(ourcpu)" -le 1200 ]; then
    for w in a b; do
      running z12$w && continue
      nohup python -u src/runner.py --plan $PL --root $B/results --worker z12$w --cpu-jobs no --threads 2 --max-jobs 1 \
        >> $B/logs/worker_z12$w.log 2>&1 &
      sleep 5
    done
  else
    echo "$(date '+%F %T') our CPU > 12 cores; not launching" >> $LOG
  fi
  sleep 20
done
