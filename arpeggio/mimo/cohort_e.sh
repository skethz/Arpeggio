#!/usr/bin/env bash
# The milestone-E repeat cohort (PROTOCOL_E.md): GPU5 only. Waits until GPU5 has no compute process (checked every
# 30 s and right before the start), then runs bench_c.py on PLAN_E_C.json and bench_d.py on PLAN_E_D.json back to back,
# with an nvidia-smi power log at 100 ms and a 20-s watchdog of compute processes; then starts the BER streams.
set -uo pipefail
R=<SCRATCH>/mimo_ising_20261016
G=<GPU_UUID>                                   # GPU5
while ! bash $R/src/gpu_free.sh $G; do sleep 30; done
export MIMO_GPU_UUID=$G
source $R/env.sh > /dev/null 2>&1
OUT=$R/results/cohort_e_$(date +%Y%m%dT%H%M%S); mkdir "$OUT" || exit 2
bash $R/src/gpu_free.sh $G || { echo "GPU $G became busy" > $OUT/gate.txt; exit 4; }
echo "$G $(nvidia-smi --query-gpu=index --format=csv,noheader -i $G) $(date '+%Y-%m-%d %H:%M:%S %Z')" > $OUT/gpu.txt
sha256sum $R/PROTOCOL_E.md $R/PLAN_E_C.json $R/PLAN_E_D.json $R/src/bench_c.py $R/src/bench_d.py $R/src/mdi_solvers.py \
  $R/src/mimo.py $R/src/anefx.py $R/src/ahcfx.py $R/src/pimi.py $R/build/ane_v2.cubin $R/build/ahc_v1.cubin \
  $R/build/pimi_v1.cubin $R/src/cohort_e.sh > $OUT/inputs.sha256
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu,power.draw --format=csv > $OUT/gpus_start.csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_start.csv
uptime > $OUT/uptime_start.txt
nvidia-smi -i $G --query-gpu=timestamp,power.draw.instant,power.draw,utilization.gpu,clocks.sm --format=csv,noheader,nounits -lms 100 > $OUT/power_smi.csv &
SMI=$!
( while kill -0 $SMI 2>/dev/null; do echo "$(date '+%H:%M:%S') $(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep "$G" | tr '\n' ' ') load $(cut -d' ' -f1 /proc/loadavg)" >> $OUT/apps_during.txt; sleep 20; done ) &
cd $R/src
python bench_c.py --plan $R/PLAN_E_C.json --ane-cubin $R/build/ane_v2.cubin --ahc-cubin $R/build/ahc_v1.cubin --out $OUT/bench_c > $OUT/bench_c.log 2>&1
echo $? > $OUT/bench_c.exit
python bench_d.py --plan $R/PLAN_E_D.json --ane-cubin $R/build/ane_v2.cubin --pimi-cubin $R/build/pimi_v1.cubin --out $OUT/bench_d > $OUT/bench_d.log 2>&1
echo $? > $OUT/bench_d.exit
kill $SMI
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv > $OUT/apps_end.csv
uptime > $OUT/uptime_end.txt
echo "cohort done $OUT"
# BER streams (untimed) start only after the cohort
G5=$G
nohup bash $R/src/run_parts_e.sh $G5 x16ahc_43 x16ahc_44 P2_47 P2_48 > $R/logs/run_parts_e_s1.log 2>&1 &
nohup bash $R/src/run_parts_e.sh $G5 x16_43 x8_43 q16_43 q8_43 P1_47 P3_47 > $R/logs/run_parts_e_s2.log 2>&1 &
nohup bash $R/src/run_parts_e.sh $G5 x16_44 x8_44 q16_44 q8_44 P1_48 P3_48 P4_47 P4_48 > $R/logs/run_parts_e_s3.log 2>&1 &
wait
