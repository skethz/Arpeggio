#!/usr/bin/env bash
# hostB supervisor (nohup; one instance): every 5 min
#  - once all 52 tuning jobs are done and results/tuned.json is absent: run select_tuned.py (PROTOCOL 4.3), then restart
#    the workers so that the tuned-variant ablation jobs become runnable (running jobs resume from their saved batches);
#  - relaunch any worker that has died (launch_hostb.sh is idempotent);
#  - guard: if MemAvailable < 210 GB, stop starting workers (log it); stop everything if < 200 GB;
#  - write results/status_hostb.txt; exit when no job is pending or running.
A=<SCRATCH>/ap_ber_20261024
LOG=$A/logs/supervisor.log
while true; do
  source $A/venv/bin/activate
  ndone=$(find $A/results/tune -name done.json 2>/dev/null | wc -l)
  if [ ! -f $A/results/tuned.json ] && [ "$ndone" -ge 52 ]; then
    echo "$(date '+%F %T') tuning complete ($ndone); selecting" >> $LOG
    python $A/src/select_tuned.py $A/results $A/results/plan_hostb_v2.json $A/results/tuned.json >> $LOG 2>&1
    pkill -f "runner.py --plan $A/results/plan_hostb_v2.json" ; sleep 10
    echo "$(date '+%F %T') workers restarted after tuning" >> $LOG
  fi
  avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
  if [ "$avail" -lt 200 ]; then
    echo "$(date '+%F %T') MemAvailable ${avail} GB < 200: stopping workers" >> $LOG; pkill -f "runner.py --plan $A/results/plan_hostb_v2.json"
  elif [ "$avail" -lt 210 ]; then
    echo "$(date '+%F %T') MemAvailable ${avail} GB < 210: not starting workers" >> $LOG
  else
    bash $A/src/launch_hostb.sh >> $LOG 2>&1
  fi
  bash $A/src/status.sh > $A/results/status_hostb.txt 2>&1
  pend=$(grep -E "^  (tab2|abl|mech|amb|tune|equiv) " $A/results/status_hostb.txt | awk '{s+=$7+$11} END{print s+0}')
  if [ "$pend" -eq 0 ]; then echo "$(date '+%F %T') nothing pending or running; supervisor exits" >> $LOG; break; fi
  sleep 300
done
