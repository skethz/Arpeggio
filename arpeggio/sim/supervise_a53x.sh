#!/usr/bin/env bash
# A5.3 Addendum 2 diagnostic (post hoc): one worker on plan_hostb_a53x.json (abl_sao_128_32, P1, seed 102). Launch only on
# a GPU with >= 6 GB free and no compute process outside ap_ber_20261024 (order GPU2, GPU1, GPU0; never GPU3); yield every
# 60 s on GPU1/GPU2 (logged); exits when the job is done.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/plan_hostb_a53x.json
LOG=$A/logs/supervisor_a5.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID>)
cd $A; source $A/venv/bin/activate
foreign() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $1 | awk -F', ' '{print $2}'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q ap_ber_20261024 || echo $p; done | wc -l; }
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
left() { python src/status.py $PL $A/results 2>/dev/null | grep -E "^  abl " | awk '{print $7+$9+$11}'; }
echo "$(date '+%F %T') A5.3x diagnostic supervisor started (pid $$)" >> $LOG
while true; do
  for i in 1 2; do
    [ "$(foreign ${G[$i]})" -eq 0 ] && continue
    for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep ${G[$i]} | awk -F', ' '{print $2}'); do
      tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q plan_hostb_a53x && { kill $p; echo "$(date '+%F %T') A5.3x: YIELD GPU$i: foreign process present; terminated our pid $p" >> $LOG; }
    done
  done
  [ "$(left)" = "0" ] && { echo "$(date '+%F %T') A5.3x complete" >> $LOG; break; }
  if ! pgrep -f "runner.py --plan $PL" > /dev/null; then
    for i in 2 1 0; do
      [ "$(foreign ${G[$i]})" -gt 0 ] && continue; [ "$(freemb ${G[$i]})" -lt 6000 ] && continue
      ( export MIMO_GPU_UUID=${G[$i]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb.sh
        nohup python -u src/runner.py --plan $PL --root $A/results --worker a53x$i --cpu-jobs no --threads 2 >> $A/logs/worker_a53x$i.log 2>&1 &
        echo "$(date '+%F %T') A5.3x: started a53x$i on GPU$i (free $(freemb ${G[$i]}) MiB)" >> $LOG )
      break
    done
  fi
  sleep 60
done
