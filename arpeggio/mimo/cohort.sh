#!/usr/bin/env bash
# The timed throughput/energy cohort (PROTOCOL.md) on GPU6, after every other job of this track has ended and only if
# GPU6 has no compute process.
set -uo pipefail
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1
for f in sweep_ddi sweep_ext coded; do while [ ! -s $R/logs/$f.exit ]; do sleep 30; done; done
OUT=$R/results/cohort_$(date +%Y%m%dT%H%M%S); mkdir "$OUT" || exit 2
sha256sum $R/PROTOCOL.md $R/src/bench.py $R/src/mimo.py $R/src/cohort.sh > $OUT/inputs.sha256
if [ -n "$(nvidia-smi -i $MIMO_GPU_UUID --query-compute-apps=pid --format=csv,noheader)" ]; then echo "GPU6 busy" > $OUT/gate.txt; exit 4; fi
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu,power.draw --format=csv > $OUT/gpus_start.csv
nvidia-smi -i $MIMO_GPU_UUID --query-gpu=timestamp,power.draw.instant,power.draw,utilization.gpu,clocks.sm --format=csv,noheader,nounits -lms 100 > $OUT/power_smi.csv &
SMI=$!
cd $R/src && python bench.py --out $OUT/bench > $OUT/bench.log 2>&1; echo $? > $OUT/bench.exit
kill $SMI
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu,power.draw --format=csv > $OUT/gpus_end.csv
echo "cohort done $OUT"
