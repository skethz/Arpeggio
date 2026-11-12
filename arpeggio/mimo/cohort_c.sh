#!/usr/bin/env bash
# The milestone-C timed cohort (PROTOCOL_C.md): waits for this track's other jobs to end, then for GPU4 or GPU7 to have
# no compute process (checked every 30 s, and once more right before the start), records which, and runs bench_c.py
# on it alone with an nvidia-smi power log at 100 ms.
set -uo pipefail
R=<SCRATCH>/mimo_ising_20261016
for f in ber_c_x16a ber_c_x16b_ahc ber_c_x16b_ane ber_c_x32a ber_c_x32b_ahc ber_c_x32b_ane ber_c_q32a ber_c_q32b ber_c_x64c equiv_c bench_c_dev_ac; do
  while [ ! -s $R/logs/$f.exit ]; do sleep 30; done; done
CANDS="<GPU_UUID> <GPU_UUID>"   # GPU4, GPU7
G=""
while [ -z "$G" ]; do
  for c in $CANDS; do if bash $R/src/gpu_free.sh $c; then G=$c; break; fi; done
  [ -z "$G" ] && sleep 30
done
export MIMO_GPU_UUID=$G
source $R/env.sh > /dev/null 2>&1
OUT=$R/results/cohort_c_$(date +%Y%m%dT%H%M%S); mkdir "$OUT" || exit 2
bash $R/src/gpu_free.sh $G || { echo "GPU $G became busy" > $OUT/gate.txt; exit 4; }
echo "$G $(nvidia-smi --query-gpu=index --format=csv,noheader -i $G) $(date '+%Y-%m-%d %H:%M:%S %Z')" > $OUT/gpu.txt
sha256sum $R/PROTOCOL_C.md $R/PLAN_C.json $R/src/bench_c.py $R/src/mdi_solvers.py $R/src/mimo.py $R/src/anefx.py \
  $R/src/ahcfx.py $R/src/ane_kernel.cu $R/src/ahc_kernel.cu $R/build/ane_v2.cubin $R/build/ahc_v1.cubin $R/src/cohort_c.sh > $OUT/inputs.sha256
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu,power.draw --format=csv > $OUT/gpus_start.csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_start.csv
uptime > $OUT/uptime_start.txt
nvidia-smi -i $G --query-gpu=timestamp,power.draw.instant,power.draw,utilization.gpu,clocks.sm --format=csv,noheader,nounits -lms 100 > $OUT/power_smi.csv &
SMI=$!
# watchdog: record any other compute process that appears on this GPU during the run
( while kill -0 $SMI 2>/dev/null; do echo "$(date '+%H:%M:%S') $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep "$G" | tr '\n' ' ')" >> $OUT/apps_during.txt; sleep 20; done ) &
cd $R/src
python bench_c.py --plan $R/PLAN_C.json --ane-cubin $R/build/ane_v2.cubin --ahc-cubin $R/build/ahc_v1.cubin --out $OUT/bench > $OUT/bench.log 2>&1 &
BP=$!; echo $BP > $OUT/bench.pid; wait $BP; echo $? > $OUT/bench.exit
kill $SMI
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_end.csv
uptime > $OUT/uptime_end.txt
echo "cohort done $OUT"
