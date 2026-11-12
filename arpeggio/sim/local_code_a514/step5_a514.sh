#!/usr/bin/env bash
# After calibration: final plan by the frozen rules, hashes appended, supervisor restarted with workers on GPU0-3.
A=<SCRATCH>/ap_ber_20261024
R=$A/results/a514
cd $A || exit 1
venv/bin/python src/plan_a514.py results/a514 || exit 2
H=$R/SHA256SUMS_A514_A516.txt
{ echo "# ADDENDUM $(date '+%F %T %Z'): calibration complete (seed 1000 only); S values are outputs of the frozen rules. No held-out batch of A* or W > 1 exists yet: $(ls -d $R/a515_c*/x32/abl_far_[0-9]*_0.1_0.1_0_rand_8 2>/dev/null | grep -vc '_far_32_') A* dirs, $(ls -d $R/a514_c* 2>/dev/null | wc -l) a514 dirs."
  sha256sum results/a514/select_a514.json results/a514/plan.json results/a514/calib_lists.json results/a514/calib_[0-9]*.json src/finish_calib_a514.py src/step5_a514.sh; } >> $H
venv/bin/python src/finish_calib_a514.py results/a514/select_a514.json > $R/SECTION11_APPENDIX.md
sha256sum results/a514/SECTION11_APPENDIX.md >> $H
old=$(cat $R/supervisor.pid); kill -TERM "$old" 2>/dev/null; sleep 2
setsid nohup bash src/supervise_a514.sh >> logs/a514/supervisor.out 2>&1 < /dev/null &
echo $! > $R/supervisor.pid
echo "supervisor $old -> $(cat $R/supervisor.pid)"
