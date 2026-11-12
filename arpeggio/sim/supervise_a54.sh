#!/usr/bin/env bash
# A5.4 supervisor (PROTOCOL_A54.md section 5). hostB GPU0 and GPU1 only; another user's job may share them, so no yielding to it.
# At most 3 workers per GPU plus one calibration process. No launch on a GPU with < 8 GB free; below 2 GB free, stop our newest worker on
# that GPU (it resumes from saved batches). Only ever signals our own a54 processes. Writes results/a54/status.txt every 5 minutes.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/a54/plan.json; ROOT=$A/results/a54; CAL=$ROOT/flips.json; LOG=$A/logs/a54/supervisor.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID>)
cd $A; source $A/venv/bin/activate
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
say() { echo "$(date '+%F %T') $*" >> $LOG; }
start_worker() {   # gpu slot
  local name=g$1$2
  pgrep -u <USER> -f "runner_a54.py --plan $PL --root $ROOT --worker $name( |$)" > /dev/null && return
  [ "$(freemb ${G[$1]})" -lt 8000 ] && { say "GPU$1 under 8 GB free; not starting $name"; return; }
  ( export MIMO_GPU_UUID=${G[$1]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb_a54.sh
    setsid nohup python -u src/runner_a54.py --plan $PL --root $ROOT --worker $name --cpu-jobs no --threads 2 >> $A/logs/a54/worker_$name.log 2>&1 &
    say "started $name on GPU$1 (free $(freemb ${G[$1]}) MiB)" )
  sleep 20
}
guard() {
  for i in 0 1; do
    [ "$(freemb ${G[$i]})" -ge 2000 ] && continue
    p=$(pgrep -u <USER> -n -f "runner_a54.py --plan $PL --root $ROOT --worker g$i")
    [ -n "$p" ] && { kill $p; say "GPU$i under 2 GB free: stopped our worker pid $p"; }
  done
}
say "A5.4 supervisor started (pid $$)"
it=0
while true; do
  guard
  if [ $((it % 5)) -eq 0 ]; then
    if ! grep -q . $A/logs/a54/calib.done 2>/dev/null && ! pgrep -u <USER> -f calib_flips_a54.py > /dev/null; then
      ( export MIMO_GPU_UUID=${G[0]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb_a54.sh
        setsid nohup bash -c "python -u src/calib_flips_a54.py $CAL >> $A/logs/a54/calib.log 2>&1 && echo done > $A/logs/a54/calib.done" > /dev/null 2>&1 &
        say "started flip calibration on GPU0" )
    fi
    python src/a54_status.py $PL $ROOT > $ROOT/status.txt.tmp 2>/dev/null && mv $ROOT/status.txt.tmp $ROOT/status.txt
    read tot don sta < <(python src/a54_status.py $PL $ROOT --brief 2>/dev/null | tail -1)
    if [ "$don" = "$tot" ] && grep -q . $A/logs/a54/calib.done 2>/dev/null; then say "A5.4 complete"; break; fi
    if [ "${sta:-0}" -gt 0 ]; then for i in 0 1; do for w in a b c; do start_worker $i $w; done; done; fi
  fi
  sleep 60; it=$((it + 1))
done
