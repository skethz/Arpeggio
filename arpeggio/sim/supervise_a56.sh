#!/usr/bin/env bash
# A5.6 supervisor (PROTOCOL_A56.md section 12). hostB GPU0 and GPU1 only. 2 workers per GPU while A5.4 runs, 4 after it ends. No launch on a GPU with
# < 8 GB free; below 2 GB free, stop our newest worker on that GPU (it resumes from saved batches). Only ever signals our own a56 processes.
A=<SCRATCH>/ap_ber_20261024
ROOT=$A/results/a56; PL=$ROOT/plan.json; LOG=$A/logs/a56/supervisor.log
declare -A G=([0]=<GPU_UUID> [1]=<GPU_UUID>)
cd $A; source $A/venv/bin/activate
freemb() { nvidia-smi --query-gpu=uuid,memory.free --format=csv,noheader,nounits | grep $1 | awk -F', ' '{print $2}'; }
say() { echo "$(date '+%F %T') $*" >> $LOG; }
start_worker() {   # gpu slot
  local name=w$1$2
  pgrep -u <USER> -f "trace_a56.py --plan $PL --root $ROOT --worker $name( |$)" > /dev/null && return
  [ "$(freemb ${G[$1]})" -lt 8000 ] && { say "GPU$1 under 8 GB free; not starting $name"; return; }
  ( export MIMO_GPU_UUID=${G[$1]} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True; source $A/env_hostb_a56.sh
    setsid nohup python -u src/trace_a56.py --plan $PL --root $ROOT --worker $name --threads 2 --mem 0.20 >> $A/logs/a56/worker_$name.log 2>&1 &
    say "started $name on GPU$1 (free $(freemb ${G[$1]}) MiB)" )
  sleep 10
}
guard() {
  for i in 0 1; do
    [ "$(freemb ${G[$i]})" -ge 2000 ] && continue
    p=$(pgrep -u <USER> -n -f "trace_a56.py --plan $PL --root $ROOT --worker w$i")
    [ -n "$p" ] && { kill $p; say "GPU$i under 2 GB free: stopped our worker pid $p"; }
  done
}
say "A5.6 supervisor started (pid $$)"
it=0
while true; do
  guard
  if [ $((it % 5)) -eq 0 ]; then
    python src/make_plan_a56.py $ROOT > /dev/null 2>> $A/logs/a56/plan.err
    python src/a56_status.py $ROOT > $ROOT/status.txt.tmp 2>/dev/null && mv $ROOT/status.txt.tmp $ROOT/status.txt
    read inplan startable fin fail3 < <(python src/a56_status.py $ROOT --brief 2>/dev/null | tail -1)
    if [ "${startable:-0}" -gt 0 ]; then
      if pgrep -u <USER> -f runner_a54.py > /dev/null; then slots="a b"; echo 4 > $A/logs/a56/x3_threads; else slots="a b c d"; echo 8 > $A/logs/a56/x3_threads; fi
      load=$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)
      if [ "$load" -ge 20 ]; then say "load $load: no new worker"; else
        for i in 0 1; do for w in $slots; do start_worker $i $w; done; done
      fi
    fi
    if [ "${inplan:-1}" = "0" ] && python - <<PY
import json,sys
sys.exit(0 if json.load(open("$A/results/a55/select.json")).get("heldout_final") else 1)
PY
    then say "A5.6 plan empty and A5.5 picks final"; python src/analyze_a56.py $ROOT 2>> $A/logs/a56/analysis.err; break; fi
  fi
  [ $((it % 30)) -eq 15 ] && python src/analyze_a56.py $ROOT 2>> $A/logs/a56/analysis.err
  sleep 60; it=$((it + 1))
done
