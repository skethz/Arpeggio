#!/usr/bin/env bash
# A5 supervisor (nohup, one instance) -- hostB GPU0 ONLY (GPU1-GPU3: other projects).
# Before every launch: if GPU0 carries any compute process outside ap_ber_20261024, launch nothing and wait.
# Order: flip calibration (seed 1000) -> merge tuned_a5.json -> 6 GPU workers + 1 CPU worker (K-sweep); every 5 min:
# selections of finished tuning families (select_a5.py; exit 10 = new pick -> restart GPU workers), relaunch finished or
# dead workers, status file; exit when the plan has nothing pending or running.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/plan_hostb_a5.json
LOG=$A/logs/supervisor_a5.log
G0=<GPU_UUID>
source $A/venv/bin/activate
foreign() {   # compute processes on GPU0 whose command line is not ours
  for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $G0 | awk -F', ' '{print $2}'); do
    tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q ap_ber_20261024 || echo $p
  done | wc -l
}
launch() {
  if [ "$(foreign)" -gt 0 ]; then echo "$(date '+%F %T') GPU0 has a foreign compute process; waiting" >> $LOG; return; fi
  for w in a b c d e f; do
    name=a5w$w
    pgrep -f "runner.py .*--worker $name( |$)" > /dev/null && continue
    ( export MIMO_GPU_UUID=$G0; source $A/env_hostb.sh
      nohup python -u src/runner.py --plan $PL --root $A/results --worker $name --cpu-jobs no --threads 2 >> $A/logs/worker_$name.log 2>&1 &
      echo "$(date '+%F %T') started $name" >> $LOG )
  done
  name=a5cpu
  if ! pgrep -f "runner.py .*--worker $name( |$)" > /dev/null; then
    ( export MIMO_GPU_UUID=$G0; source $A/env_hostb.sh; export NUMBA_NUM_THREADS=8
      nohup python -u src/runner.py --plan $PL --root $A/results --worker $name --cpu-jobs only --threads 1 >> $A/logs/worker_$name.log 2>&1 &
      echo "$(date '+%F %T') started $name" >> $LOG )
  fi
}
until [ "$(foreign)" -eq 0 ]; do echo "$(date '+%F %T') GPU0 busy (foreign); waiting to calibrate" >> $LOG; sleep 300; done
if [ ! -f $A/results/a5_flip_phi.json ]; then
  ( export MIMO_GPU_UUID=$G0; source $A/env_hostb.sh; python -u src/calib_flips.py $A/results/a5_flip_phi.json >> $LOG 2>&1 )
fi
python $A/src/select_a5.py $A/results $PL >> $LOG 2>&1
launch
while true; do
  sleep 300
  python $A/src/select_a5.py $A/results $PL pt sa2 dim symd qdim_pp colx16 colx32 >> $LOG 2>&1
  if [ $? -eq 10 ]; then
    pkill -f "runner.py --plan $PL .*--cpu-jobs no"; sleep 10; echo "$(date '+%F %T') new tuning pick; GPU workers restarted" >> $LOG
  fi
  python $A/src/status.py $PL $A/results > $A/results/status_a5.txt 2>&1
  left=$(grep -E "^  (tab2|abl|tune|mech) " $A/results/status_a5.txt | awk '{s+=$7+$11} END{print s+0}')
  [ "$left" -eq 0 ] && { echo "$(date '+%F %T') A5 complete; supervisor exits" >> $LOG; break; }
  launch
done
