#!/usr/bin/env bash
# The milestone-B timed cohort (PROTOCOL_B.md): waits until GPU4 or GPU7 has no compute process (checked
# every 30 s), records which, and runs bench_b.py on it alone, with an nvidia-smi power log at 100 ms.
set -uo pipefail
R=<SCRATCH>/mimo_ising_20261016
CANDS="<GPU_UUID> <GPU_UUID>"   # GPU4, GPU7 (GPU5: another project, 12:24)
for f in sweep_mdi_x16a sweep_mdi_x16b sweep_mdi_x32a run_mdi64; do while [ ! -s $R/logs/$f.exit ]; do sleep 30; done; done
G=""
while [ -z "$G" ]; do
  for c in $CANDS; do if bash $R/src/gpu_free.sh $c; then G=$c; break; fi; done
  [ -z "$G" ] && sleep 30
done
export MIMO_GPU_UUID=$G
source $R/env.sh > /dev/null 2>&1
OUT=$R/results/cohort_b_$(date +%Y%m%dT%H%M%S); mkdir "$OUT" || exit 2
echo "$G $(nvidia-smi --query-gpu=index --format=csv,noheader -i $G) $(date '+%Y-%m-%d %H:%M:%S %Z')" > $OUT/gpu.txt
sha256sum $R/PROTOCOL_B.md $R/PLAN_B.json $R/src/bench_b.py $R/src/anefx.py $R/src/fxdetect.py $R/src/mimo.py $R/src/tree.py \
  $R/src/ane_kernel.cu $R/build/ane_v2.cubin $R/src/cohort_b.sh > $OUT/inputs.sha256
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu,power.draw --format=csv > $OUT/gpus_start.csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_start.csv
uptime > $OUT/uptime_start.txt
nvidia-smi -i $G --query-gpu=timestamp,power.draw.instant,power.draw,utilization.gpu,clocks.sm --format=csv,noheader,nounits -lms 100 > $OUT/power_smi.csv &
SMI=$!
cd $R/src && python bench_b.py --plan $R/PLAN_B.json --cubin $R/build/ane_v2.cubin --out $OUT/bench > $OUT/bench.log 2>&1; echo $? > $OUT/bench.exit
kill $SMI
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_end.csv
uptime > $OUT/uptime_end.txt
echo "cohort done $OUT"
