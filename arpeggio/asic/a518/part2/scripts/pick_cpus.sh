#!/bin/bash
# print a comma list of N CPUs that mpstat shows > 90% idle over 3 s (highest-numbered idle ones)
N=${1:-4}; mpstat -P ALL 1 3 | awk '/Average/ && $2 ~ /^[0-9]+$/ && $NF > 90 {print $2}' | tail -n $N | paste -sd,
