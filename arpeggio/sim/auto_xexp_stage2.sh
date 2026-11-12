#!/usr/bin/env bash
# A3 stage-2 trigger (nohup, one-shot): when all 54 xtune jobs are done, run select_xexp.py (writes plan_hostb_xexp_v2.json:
# held-out seed-102 picks + A4 grid extension), stop the stage-1 workers and start 6 workers (GPU0/1/2) on the v2 plan.
A=<SCRATCH>/ap_ber_20261024
LOG=$A/logs/xexp_stage2.log
source $A/venv/bin/activate
until [ "$(find $A/results/xtune -name done.json | wc -l)" -ge 54 ]; do sleep 60; done
echo "$(date '+%F %T') stage 1 complete" >> $LOG
python $A/src/select_xexp.py $A/results $A/results/plan_hostb_xexp.json $A/results/plan_hostb_xexp_v2.json >> $LOG 2>&1 || exit 1
pkill -f "runner.py --plan $A/results/plan_hostb_xexp.json"; sleep 5
GPUS="0 1 2" bash $A/src/launch_xexp.sh plan_hostb_xexp_v2.json >> $LOG 2>&1
echo "$(date '+%F %T') stage-2 workers started" >> $LOG
# keep relaunching finished/dead stage-2 workers until no xheld/A4 job is pending (idempotent launcher)
while true; do
  sleep 300
  n=$(python - << PY
import json, os
p = json.load(open('$A/results/plan_hostb_xexp_v2.json'))
left = 0
for j in p['jobs']:
    d = os.path.join('$A/results', j['set'], j['shape'], j['method'], 'snr_%05.2f' % j['snr'])
    if not os.path.exists(os.path.join(d, 'done.json')):
        left += 1
print(left)
PY
)
  echo "$(date '+%F %T') stage-2 jobs left: $n" >> $LOG
  [ "$n" -eq 0 ] && { echo "$(date '+%F %T') all A3/A4 jobs done" >> $LOG; break; }
  GPUS="0 1 2" bash $A/src/launch_xexp.sh plan_hostb_xexp_v2.json >> $LOG 2>&1
done
