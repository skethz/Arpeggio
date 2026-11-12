#!/usr/bin/env bash
# A5.3d supervisor (PROTOCOL_A53.md Addendum 1): LOWEST priority. Waits (polling every 5 min) until A5 tier 1 is complete
# (a5_left.py tier1_left 0) AND A5.3 (a)-(c) are complete (plan_hostb_a53.json has no running/failed/pending job and the
# flip calibration has all 32 entries). Then runs plan_hostb_a53d.json (3 jobs) with at most 3 workers a53d<gpu><a|b|c>,
# one per GPU, each launched only on a GPU with >= 6 GB free, no compute process outside ap_ber_20261024 and no other
# A5.3/A5.3d process; GPU order 1, 2, 0; never GPU3; CPU guard 20 cores. Yield every 60 s on GPU1/GPU2 (terminate ours on
# a GPU that gains a foreign process; logged; jobs resume from saved batches). Exits when the plan is done.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/plan_hostb_a53d.json
P53=$A/results/plan_hostb_a53.json
CAL=$A/results/a53_flips_sa.json
LOG=$A/logs/supervisor_a5.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID>)
cd $A
source $A/venv/bin/activate
foreign() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $1 | awk -F', ' '{print $2}'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q ap_ber_20261024 || echo $p; done | wc -l; }
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
ourcpu() { ps -eo pcpu,args | grep "ap_ber_20261024" | grep -v grep | awk '{s+=$1} END{print int(s)}'; }
ours53() { for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep $1 | awk -F', ' '{print $2}'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -qE "plan_hostb_a53|calib_flips_sa" && echo $p; done | wc -l; }
pickgpu() { for i in 1 2 0; do [ "$(foreign ${G[$i]})" -gt 0 ] && continue; [ "$(ours53 ${G[$i]})" -gt 0 ] && continue; [ "$(freemb ${G[$i]})" -lt 6000 ] && continue; echo $i; return; done; echo none; }
left_of() { python src/status.py $1 $A/results 2>/dev/null | grep -E "^  (abl|tab2) " | awk -v c="$2" '{if (c=="pend") s+=$11; else s+=$7+$9+$11} END{print s+0}'; }
gate() {
  [ "$(python src/a5_left.py | awk '{print $2}')" = "0" ] || return 1
  [ "$(left_of $P53 all)" -eq 0 ] || return 1
  python -c "import json,sys; sys.exit(0 if len(json.load(open('$CAL'))['F'])==32 else 1)" 2>/dev/null
}
launch() {
  [ "$(ourcpu)" -gt 2000 ] && { echo "$(date '+%F %T') A5.3d: our CPU > 20 cores; not launching" >> $LOG; return; }
  for w in a b c; do
    [ "$(pgrep -f "runner.py --plan $PL" | wc -l)" -ge 3 ] && return
    # unfinished jobs (pending + claimed, including stale claims of yielded workers) must exceed live workers; a new
    # worker reclaims a stale claim (same host, dead pid) and resumes from its saved batches (v2 fix, Mon 26 Oct 01:5x)
    [ "$(left_of $PL all)" -le "$(pgrep -f "runner.py --plan $PL" | wc -l)" ] && return
    i=$(pickgpu); [ "$i" = none ] && return
    name=a53d$i$w
    pgrep -f "runner.py .*--worker $name( |$)" > /dev/null && continue
    ( export MIMO_GPU_UUID=${G[$i]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb.sh
      nohup python -u src/runner.py --plan $PL --root $A/results --worker $name --cpu-jobs no --threads 2 >> $A/logs/worker_$name.log 2>&1 &
      echo "$(date '+%F %T') A5.3d: started $name on GPU$i (free $(freemb ${G[$i]}) MiB)" >> $LOG )
    sleep 30
  done
}
yield() {
  for i in 1 2; do
    [ "$(foreign ${G[$i]})" -eq 0 ] && continue
    for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep ${G[$i]} | awk -F', ' '{print $2}'); do
      if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q "plan_hostb_a53d"; then
        kill $p; echo "$(date '+%F %T') A5.3d: YIELD GPU$i: foreign process present; terminated our pid $p" >> $LOG
      fi
    done
  done
}
echo "$(date '+%F %T') A5.3d supervisor started (pid $$); waiting for A5 tier 1 and A5.3 (a)-(c)" >> $LOG
until gate; do sleep 300; done
echo "$(date '+%F %T') A5.3d: gate open (A5 tier 1 and A5.3 (a)-(c) complete)" >> $LOG
it=0
launch
while true; do
  sleep 60; it=$((it + 1))
  yield
  if [ "$(left_of $PL all)" -eq 0 ]; then echo "$(date '+%F %T') A5.3d complete" >> $LOG; break; fi
  [ $((it % 5)) -eq 0 ] && launch
done
