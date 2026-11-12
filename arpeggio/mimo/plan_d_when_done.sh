#!/usr/bin/env bash
# After every BER part has ended, build PLAN_D.json by PROTOCOL_D's rules (src/make_plan_d.py) from the seed-42 results.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1
for f in x16_a x16_ahc x8_a q16_a q8_a P1_b P2_b P3_b P4_b; do while [ ! -s $R/logs/ber_d_$f.exit ]; do sleep 30; done; done
cd $R/src && python make_plan_d.py $R/results/ber_d $R/PLAN_D.json > $R/logs/make_plan_d.log 2>&1; echo $? >> $R/logs/make_plan_d.log
sha256sum $R/PLAN_D.json >> $R/logs/make_plan_d.log
