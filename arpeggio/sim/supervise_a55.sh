#!/usr/bin/env bash
# A5.5 supervisor (PROTOCOL_A55.md section 11). hostB GPU2 and GPU3, plus GPU0 and GPU1 since 6 Nov 2026 (author: "<instruction>"; reruns of
# finished cells on GPU0 and GPU1 matched the saved batches bit for bit, tmp/gpu01_check_20261106); another user's job may share them, so no yielding to it.
# At most 4 workers per GPU plus one calibration process. No launch on a GPU with < 8 GB free; below 2 GB free, stop our newest worker on
# that GPU (it resumes from saved batches). Only ever signals our own a55 processes. Rebuilds the plan and status every 2 minutes.
A=<SCRATCH>/ap_ber_20261024
ROOT=$A/results/a55; PL=$ROOT/plan.json; LOG=$A/logs/a55/supervisor.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID> [2]=<GPU_UUID> [3]=<GPU_UUID>)
cd $A; source $A/venv/bin/activate
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
say() { echo "$(date '+%F %T') $*" >> $LOG; }
start_worker() {   # gpu slot
  local name=g$1$2
  pgrep -u <USER> -f "runner_a55.py --plan $PL --root $ROOT --worker $name( |$)" > /dev/null && return
  [ "$(freemb ${G[$1]})" -lt 8000 ] && { say "GPU$1 under 8 GB free; not starting $name"; return; }
  ( export MIMO_GPU_UUID=${G[$1]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True A55_MEM_FRAC=0.20; source $A/env_hostb_a55.sh
    setsid nohup python -u src/runner_a55.py --plan $PL --root $ROOT --worker $name --cpu-jobs no --threads 2 >> $A/logs/a55/worker_$name.log 2>&1 &
    say "started $name on GPU$1 (free $(freemb ${G[$1]}) MiB)" )
  sleep 5
}
guard() {
  for i in 0 1 2 3; do
    [ "$(freemb ${G[$i]})" -ge 2000 ] && continue
    p=$(pgrep -u <USER> -n -f "runner_a55.py --plan $PL --root $ROOT --worker g$i")
    [ -n "$p" ] && { kill $p; say "GPU$i under 2 GB free: stopped our worker pid $p"; }
  done
}
say "A5.5 supervisor started (pid $$)"
while true; do
  guard
  read tot sta fin < <(python src/a55_plan.py $ROOT 2>> $A/logs/a55/plan.err | tail -1)
  python src/a55_status.py $ROOT > $ROOT/status.txt.tmp 2>/dev/null && mv $ROOT/status.txt.tmp $ROOT/status.txt
  if python -c "import json,sys;sys.exit(0 if json.load(open('$ROOT/select.json')).get('heldout_final') else 1)" 2>/dev/null \
     && ! grep -q . $A/logs/a55/calib.done 2>/dev/null && ! pgrep -u <USER> -f calib_flips_a55.py > /dev/null; then
    ( export MIMO_GPU_UUID=${G[3]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True A55_MEM_FRAC=0.20; source $A/env_hostb_a55.sh
      setsid nohup bash -c "python -u src/calib_flips_a55.py $ROOT/flips.json $ROOT/select.json >> $A/logs/a55/calib.log 2>&1 && echo done > $A/logs/a55/calib.done" > /dev/null 2>&1 &
      say "started flip calibration on GPU3" )
  fi
  if [ "${fin:-0}" = "1" ] && grep -q . $A/logs/a55/calib.done 2>/dev/null; then say "A5.5 complete"; break; fi
  if [ "${sta:-0}" -gt 0 ]; then for i in 2 3 0 1; do for w in a b c d; do start_worker $i $w; done; done; fi
  sleep 120
done
