#!/usr/bin/env bash
# A5 companion supervisor (author's permission, 24 Oct 23:46): use hostB GPU1/GPU2 ONLY while they carry no compute process
# outside ap_ber_20261024; GPU3 never. Every 60 s: on a GPU with a foreign process, terminate our workers there (yield) and
# do not launch; every 5 min: on a fully idle GPU, start up to 4 workers (UUID-bound; 4 not 6, to keep our total CPU
# <= 24 cores: we also run 6 workers on GPU0 and the K-best CPU worker) unless our processes already use > 20 cores.
# Killed workers leave claim.json + saved batches; the runner on any host GPU reclaims a dead worker's claim (same host,
# pid not alive) and resumes from the saved batches (draws and solver seeds depend only on seed/SNR/batch/method).
# Exits (after stopping its workers) when the main A5 supervisor has exited.
A=<SCRATCH>/ap_ber_20261024
PL=$A/results/plan_hostb_a5.json
LOG=$A/logs/supervisor_a5.log
declare -A G=([1]=<GPU_UUID> [2]=<GPU_UUID>)
NPER=4
foreign() {
  for p in $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep "$1" | awk -F', ' '{print $2}'); do
    tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q ap_ber_20261024 || echo $p
  done | wc -l
}
ourcpu() { ps -eo pcpu,args | grep "ap_ber_20261024" | grep -v grep | awk '{s+=$1} END{print int(s)}'; }
it=0
while true; do
  if ! pgrep -f "bash src/supervise_a5.sh" > /dev/null; then
    for i in 1 2; do pkill -f "runner.py .*--worker a5x${i}[a-f]( |$)"; done
    echo "$(date '+%F %T') extra: main supervisor gone; extra workers stopped; exiting" >> $LOG; break
  fi
  for i in 1 2; do
    n=$(pgrep -f "runner.py .*--worker a5x${i}[a-f]( |$)" | wc -l)
    f=$(foreign ${G[$i]})
    if [ "$f" -gt 0 ] && [ "$n" -gt 0 ]; then
      pkill -f "runner.py .*--worker a5x${i}[a-f]( |$)"
      echo "$(date '+%F %T') extra: YIELD GPU$i (${G[$i]}): $f foreign process(es); stopped $n of our workers" >> $LOG
    elif [ "$f" -eq 0 ] && [ $((it % 5)) -eq 0 ]; then
      cpu=$(ourcpu)
      if [ "$cpu" -gt 2000 ]; then echo "$(date '+%F %T') extra: GPU$i idle but our CPU ${cpu}% > 2000%; not adding" >> $LOG; continue; fi
      for w in a b c d e f; do
        [ $(pgrep -f "runner.py .*--worker a5x${i}[a-f]( |$)" | wc -l) -ge $NPER ] && break
        name=a5x${i}$w
        pgrep -f "runner.py .*--worker $name( |$)" > /dev/null && continue
        [ "$(foreign ${G[$i]})" -gt 0 ] && break
        ( export MIMO_GPU_UUID=${G[$i]}; source $A/env_hostb.sh
          nohup python -u src/runner.py --plan $PL --root $A/results --worker $name --cpu-jobs no --threads 2 >> $A/logs/worker_$name.log 2>&1 &
          echo "$(date '+%F %T') extra: ADD $name on GPU$i (${G[$i]}), GPU fully idle" >> $LOG )
      done
    fi
  done
  it=$((it + 1))
  sleep 60
done
