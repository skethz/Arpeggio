#!/usr/bin/env bash
# A5.3 supervisor (exploratory; PROTOCOL_A53.md). At most 3 processes of ours for A5.3: runner workers a53g<gpu><a|b|c> on
# plan_hostb_a53.json plus, until it has finished, one flip-calibration process (calib_flips_sa.py, counts as one slot).
# Launch only on a GPU with >= 6 GB free, NO compute process outside ap_ber_20261024 and no other A5.3 process (one A5.3
# process per GPU, so A5 workers keep headroom to grow; order GPU1, GPU2, GPU0; never GPU3); CPU guard: no launch while our processes use > 20 cores. Yield (every 60 s): on GPU1/GPU2, if a foreign process
# appears, terminate every A5.3 process of ours on that GPU (workers resume later from saved batches via the stale-claim
# reclaim; the calibration resumes from its per-entry JSON). A5 workers are never touched. Exits when the plan and the
# calibration are done.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/plan_hostb_a53.json
CAL=$A/results/a53_flips_sa.json
LOG=$A/logs/supervisor_a5.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID>)
cd $A
source $A/venv/bin/activate
foreign() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $1 | awk -F', ' '{print $2}'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q ap_ber_20261024 || echo $p; done | wc -l; }
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
ourcpu() { ps -eo pcpu,args | grep "ap_ber_20261024" | grep -v grep | awk '{s+=$1} END{print int(s)}'; }
nslots() { echo $(( $(pgrep -f "runner.py --plan $PL" | wc -l) + $(pgrep -f "calib_flips_sa.py" | wc -l) )); }
caldone() { [ -f $CAL ] && python -c "import json,sys; sys.exit(0 if len(json.load(open('$CAL'))['F'])==32 else 1)"; }
ours53() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $1 | awk -F', ' '{print $2}'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -qE "plan_hostb_a53|calib_flips_sa" && echo $p; done | wc -l; }
pickgpu() { for i in 1 2 0; do [ "$(foreign ${G[$i]})" -gt 0 ] && continue; [ "$(ours53 ${G[$i]})" -gt 0 ] && continue; [ "$(freemb ${G[$i]})" -lt 6000 ] && continue; echo $i; return; done; echo none; }
launch() {
  [ "$(ourcpu)" -gt 2000 ] && { echo "$(date '+%F %T') A5.3: our CPU > 20 cores; not launching" >> $LOG; return; }
  if ! caldone && ! pgrep -f calib_flips_sa.py > /dev/null && [ "$(nslots)" -lt 3 ]; then
    i=$(pickgpu); [ "$i" = none ] && return
    ( export MIMO_GPU_UUID=${G[$i]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb.sh
      nohup python -u src/calib_flips_sa.py $CAL >> $A/logs/a53_calib_g$i.log 2>&1 &
      echo "$(date '+%F %T') A5.3: started flip calibration on GPU$i (free $(freemb ${G[$i]}) MiB)" >> $LOG )
    sleep 30
  fi
  for w in a b c; do
    [ "$(nslots)" -ge 3 ] && return
    left=$(python src/status.py $PL $A/results 2>/dev/null | grep -E "^  (abl|tab2) " | awk '{s+=$11} END{print s+0}')
    [ "$left" -eq 0 ] && return
    i=$(pickgpu); [ "$i" = none ] && return
    name=a53g$i$w
    pgrep -f "runner.py .*--worker $name( |$)" > /dev/null && continue
    ( export MIMO_GPU_UUID=${G[$i]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb.sh
      nohup python -u src/runner.py --plan $PL --root $A/results --worker $name --cpu-jobs no --threads 2 >> $A/logs/worker_$name.log 2>&1 &
      echo "$(date '+%F %T') A5.3: started $name on GPU$i (free $(freemb ${G[$i]}) MiB)" >> $LOG )
    sleep 30
  done
}
yield() {
  for i in 1 2; do
    [ "$(foreign ${G[$i]})" -eq 0 ] && continue
    for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep ${G[$i]} | awk -F', ' '{print $2}'); do
      if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -qE "plan_hostb_a53|calib_flips_sa"; then
        kill $p; echo "$(date '+%F %T') A5.3: YIELD GPU$i: foreign process present; terminated our pid $p" >> $LOG
      fi
    done
  done
}
echo "$(date '+%F %T') A5.3 supervisor started (pid $$)" >> $LOG
it=0
launch
while true; do
  sleep 60; it=$((it + 1))
  yield
  left=$(python src/status.py $PL $A/results 2>/dev/null | grep -E "^  (abl|tab2) " | awk '{s+=$7+$9+$11} END{print s+0}')
  if [ "$left" -eq 0 ] && caldone; then echo "$(date '+%F %T') A5.3 complete" >> $LOG; break; fi
  [ $((it % 5)) -eq 0 ] && launch
done
