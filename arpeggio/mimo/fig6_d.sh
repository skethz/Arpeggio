#!/usr/bin/env bash
# Fig. 6 validation (PROTOCOL_D: not held-out comparisons): our PIMI on the authors' instances and on our port of their
# channel model; then our BER evaluation of their own solved states against their report.json. Usage: fig6_d.sh UUID
export MIMO_GPU_UUID=$1 CUDA_VISIBLE_DEVICES=$1; R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src
while ! grep -q CACHE_DONE $R/logs/cache_pimi_instances.log; do sleep 20; done
python check_pimi_reports.py $R/results/pimi_their_instances $R/baselines/pimi_zenodo/reports/reports_all.jsonl $R/results/pimi_fig6_d/reports_check.jsonl > $R/results/pimi_fig6_d/reports_check.log 2>&1; echo "check exit $?" >> $R/results/pimi_fig6_d/reports_check.log
python run_pimi_fig6.py --cache $R/results/pimi_their_instances --out $R/results/pimi_fig6_d/fig6 --sources their_instances,our_generator
echo FIG6_DONE $? $(date '+%H:%M:%S %Z')
