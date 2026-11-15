#!/usr/bin/env bash
# After calibration: final plan by the S rules, hashes appended, supervisor restarted with workers on GPU0-3.
A=<SCRATCH>/arpeggio_ber_20261024
R=$A/results/a514
cd $A || exit 1
venv/bin/python src/plan_a514.py results/a514 || exit 2
H=$R/SHA256SUMS_A514_A516.txt
{ echo "# $(date '+%F %T %Z'): calibration complete (seed 1000 only); S values are outputs of the calibration rules."
  sha256sum results/a514/select_a514.json results/a514/plan.json results/a514/calib_lists.json results/a514/calib_[0-9]*.json src/finish_calib_a514.py src/step5_a514.sh; } >> $H
venv/bin/python src/finish_calib_a514.py results/a514/select_a514.json > $R/S_RULES.md
sha256sum results/a514/S_RULES.md >> $H
old=$(cat $R/supervisor.pid); kill -TERM "$old" 2>/dev/null; sleep 2
setsid nohup bash src/supervise_a514.sh >> logs/a514/supervisor.out 2>&1 < /dev/null &
echo $! > $R/supervisor.pid
echo "supervisor $old -> $(cat $R/supervisor.pid)"
