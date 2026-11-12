#!/usr/bin/env bash
# Run milestone-E BER parts in sequence on GPU5 (untimed; up to three such streams share GPU5 after the cohort).
# Usage: run_parts_e.sh UUID PART...
R=<SCRATCH>/mimo_ising_20261016; U=$1; shift
for p in "$@"; do
  bash $R/src/ber_e.sh $p $U > $R/logs/ber_e_$p.log 2>&1; echo $? > $R/logs/ber_e_$p.exit
done
