#!/bin/bash
# Full RTL regression (current rtl/ape_engine.sv) against the stored vector sets; writes vec/regress_<tag>.txt
R=<SCRATCH>/antiphase_asic_20261017; cd $R/ape; export TMPDIR=$R/tmp; T=$1
run() { bash tb/run_sim.sh $@ > $1_$6.log 2>&1; }
run vec/x16_philox 32 4 1 philox bug &
run vec/x16_philox 32 4 1 philox engine &
run vec/x16_xs 32 4 1 xs engine &
run vec/x16b_philox 32 4 1 philox engine &
run vec/x16b_xs 32 4 1 xs engine &
run vec/x16_xs_A2 32 2 1 xs engine &
run vec/q32_philox 64 4 2 philox engine &
run vec/x32_philox 64 4 2 philox engine &
run vec/x32_xs 64 4 2 xs engine &
run vec/x64_philox 128 4 4 philox engine &
run vec/x64_xs 128 4 4 xs engine &
wait
out=vec/regress_$T.txt; : > $out
for f in vec/x16_philox_bug.log vec/x16_philox_engine.log vec/x16_xs_engine.log vec/x16b_philox_engine.log vec/x16b_xs_engine.log vec/x16_xs_A2_engine.log vec/q32_philox_engine.log vec/x32_philox_engine.log vec/x32_xs_engine.log vec/x64_philox_engine.log vec/x64_xs_engine.log; do
  echo "$f: $(grep -E '^SUMMARY' $f || echo 'no summary') | $(grep -E '^(PASS|FAIL) reference' $f | cut -c1-90)" >> $out; done
cat $out
