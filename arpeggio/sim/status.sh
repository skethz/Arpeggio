#!/usr/bin/env bash
# One-line-per-set status of this host's plan plus running jobs, GPU use and worker processes. Usage: status.sh
A=<SCRATCH>/ap_ber_20261024
H=$(hostname -s)
source $A/venv/bin/activate 2>/dev/null || source <SCRATCH>/mimo_ising_20261016/venv/bin/activate
P=$A/results/plan_$H.json; [ -f $A/results/plan_${H}_v2.json ] && P=$A/results/plan_${H}_v2.json; python $A/src/status.py $P $A/results --json $A/results/status_$H.json
echo "workers:"; pgrep -af "runner.py" | sed 's/--plan.*--worker/ worker/' | cut -c1-80
nvidia-smi --query-gpu=index,uuid,utilization.gpu,memory.used --format=csv,noheader | grep -E "0f7cbc13|520ad98b|b6098673|bfc8c63b"
uptime
