#!/usr/bin/env bash
# A5.2 supervisor (nohup), v2 (Sun 25 Oct): v1 ran 3 workers on GPU0 and hit CUDA out-of-memory (the six A5 workers hold
# about 28 GB there); the failed attempts are kept as failed.*.json and the jobs are simply retried. v2 starts at most 2
# workers, each on a GPU with >= 8 GB free: GPU1/GPU2 only while they carry no compute process outside ap_ber_20261024,
# else GPU0; never GPU3. CPU guard: no launch while our processes use > 20 cores. Stage 1 = extension cells; when all are
# done, select_a52.py writes the picks and the workers are restarted for the held-out re-runs; exits when the plan is done.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/plan_hostb_a52.json
LOG=$A/logs/supervisor_a5.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID>)
source $A/venv/bin/activate
foreign() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $1 | awk -F', ' '{print $2}'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q ap_ber_20261024 || echo $p; done | wc -l; }
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
ourcpu() { ps -eo pcpu,args | grep "ap_ber_20261024" | grep -v grep | awk '{s+=$1} END{print int(s)}'; }
cp -n $A/results/tuned_a5.json $A/results/tuned_a52.json 2>/dev/null
launch() {
  [ "$(ourcpu)" -gt 2000 ] && { echo "$(date '+%F %T') A5.2: our CPU > 20 cores; not launching" >> $LOG; return; }
  for w in a b; do
    name=a52v$w
    pgrep -f "runner.py .*--worker $name( |$)" > /dev/null && continue
    for i in 1 2 0; do
      [ "$(foreign ${G[$i]})" -gt 0 ] && continue
      [ "$(freemb ${G[$i]})" -lt 8000 ] && continue
      ( export MIMO_GPU_UUID=${G[$i]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb.sh
        nohup python -u src/runner.py --plan $PL --root $A/results --worker $name --cpu-jobs no --threads 2 >> $A/logs/worker_$name.log 2>&1 &
        echo "$(date '+%F %T') A5.2: started $name on GPU$i (free $(freemb ${G[$i]}) MiB)" >> $LOG )
      sleep 20
      break
    done
  done
}
launch
while true; do
  sleep 120
  python $A/src/select_a52.py $A/results >> $LOG 2>&1
  if [ $? -eq 10 ]; then pkill -f "runner.py --plan $PL"; sleep 5; echo "$(date '+%F %T') A5.2: picks written; workers restarted" >> $LOG; fi
  left=$(python $A/src/status.py $PL $A/results 2>/dev/null | grep -E "^  (abl|tune) " | awk '{s+=$7+$9+$11} END{print s+0}')
  [ "$left" -eq 0 ] && { echo "$(date '+%F %T') A5.2 complete" >> $LOG; break; }
  launch
done
