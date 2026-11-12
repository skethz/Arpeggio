#!/usr/bin/env bash
# The milestone-D timed cohort (PROTOCOL_D.md): waits for this track's BER parts to end, then for GPU4 or GPU5 to have
# no compute process (checked every 30 s, and once more right before the start), records which, and runs bench_d.py
# on it alone with an nvidia-smi power log at 100 ms and a 20-s watchdog of compute processes.
set -uo pipefail
R=<SCRATCH>/mimo_ising_20261016
for f in ber_d_x16_a ber_d_x16_ahc ber_d_x8_a ber_d_q16_a ber_d_q8_a ber_d_P1_b ber_d_P2_b ber_d_P3_b ber_d_P4_b; do
  while [ ! -s $R/logs/$f.exit ]; do sleep 30; done; done
while [ ! -s $R/PLAN_D.json ]; do sleep 30; done
CANDS="<GPU_UUID> <GPU_UUID>"   # GPU4, GPU5
G=""
while [ -z "$G" ]; do
  for c in $CANDS; do if bash $R/src/gpu_free.sh $c; then G=$c; break; fi; done
  [ -z "$G" ] && sleep 30
done
export MIMO_GPU_UUID=$G
source $R/env.sh > /dev/null 2>&1
OUT=$R/results/cohort_d_$(date +%Y%m%dT%H%M%S); mkdir "$OUT" || exit 2
bash $R/src/gpu_free.sh $G || { echo "GPU $G became busy" > $OUT/gate.txt; exit 4; }
echo "$G $(nvidia-smi --query-gpu=index --format=csv,noheader -i $G) $(date '+%Y-%m-%d %H:%M:%S %Z')" > $OUT/gpu.txt
sha256sum $R/PROTOCOL_D.md $R/PLAN_D.json $R/src/bench_d.py $R/src/pimi.py $R/src/mdi_solvers.py $R/src/mimo.py $R/src/anefx.py \
  $R/src/pimi_kernel.cu $R/src/ane_kernel.cu $R/build/pimi_v1.cubin $R/build/ane_v2.cubin $R/src/cohort_d.sh > $OUT/inputs.sha256
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu,power.draw --format=csv > $OUT/gpus_start.csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_start.csv
uptime > $OUT/uptime_start.txt
nvidia-smi -i $G --query-gpu=timestamp,power.draw.instant,power.draw,utilization.gpu,clocks.sm --format=csv,noheader,nounits -lms 100 > $OUT/power_smi.csv &
SMI=$!
( while kill -0 $SMI 2>/dev/null; do echo "$(date '+%H:%M:%S') $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep "$G" | tr '\n' ' ')" >> $OUT/apps_during.txt; sleep 20; done ) &
cd $R/src
python bench_d.py --plan $R/PLAN_D.json --ane-cubin $R/build/ane_v2.cubin --pimi-cubin $R/build/pimi_v1.cubin --out $OUT/bench > $OUT/bench.log 2>&1 &
BP=$!; echo $BP > $OUT/bench.pid; wait $BP; echo $? > $OUT/bench.exit
kill $SMI
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_end.csv
uptime > $OUT/uptime_end.txt
echo "cohort done $OUT"
