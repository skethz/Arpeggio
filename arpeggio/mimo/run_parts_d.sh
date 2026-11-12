#!/usr/bin/env bash
# Run milestone-D BER parts in sequence on one GPU (each GPU checked free first). Usage: run_parts_d.sh UUID PART...
R=<SCRATCH>/mimo_ising_20261016; U=$1; shift
for p in "$@"; do
  while ! bash $R/src/gpu_free.sh $U; do sleep 30; done
  bash $R/src/ber_d.sh $p $U > $R/logs/ber_d_$p.log 2>&1; echo $? > $R/logs/ber_d_$p.exit
done
