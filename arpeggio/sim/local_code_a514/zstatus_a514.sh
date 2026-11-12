#!/usr/bin/env bash
# Prints hostA's overflow status and whether its supervisor (pid file) is alive. Read-only.
Z=<SCRATCH>/ap_ber_20261024/a514z
cat $Z/results/a514/status.txt
if kill -0 "$(cat $Z/results/a514/supervisor.pid)" 2>/dev/null; then echo SUPERVISOR_ALIVE; else echo SUPERVISOR_GONE; fi
