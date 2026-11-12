#!/bin/bash
# RTL activity (SAIF) of a detection stream for power: production build, clock period PER ps (default 1000; the SAIF is
# simulated at the layout period of the corner, so Genus reads it with scale 1.0), window = from the acceptance of the
# first command after the one-time schedule-table load to the model's last cycle. Also checks the run against the model
# (tb/compare.py). usage: run_saif.sh <stim dir> <D> <SEEDL> <tag> [period ps]   (from ape/)
set -e
V=$1; D=$2; SL=$3; T=$4; PER=${5:-1000}; H=$(pwd)
HALF=$(python3 -c "print(${PER} / 2000.0)")
W=$V/saif_$T; rm -rf $W; mkdir -p $W; cd $W; cp ../stim.txt ../expected.json .
read TS TE < <($H/../venv/bin/python -c "
import json; e=json.load(open('expected.json')); f=e['first_work_cmd']
print(int(round((4.5 + e['acc'][f] - 0.25) * $PER)), int(round((4.5 + e['cycles'] - 0.25) * $PER)))")
questa-2025.3 vlib work > vlog.log 2>&1
questa-2025.3 vlog -sv +define+CLK_HALF_NS=$HALF $H/rtl/ape_mem_behav.sv $H/rtl/ape_engine.sv $H/tb/tb_ape.sv >> vlog.log 2>&1
cat > saif.do <<EOD
power add -in -out -inout -internal -r /tb_ape/dut/*
run ${TS}ps
power report -all -bsaif A.saif
run $((TE-TS))ps
power report -all -bsaif B.saif
run -all
quit -f
EOD
questa-2025.3 vsim -c -voptargs=+acc -GD=$D -GA=4 -GSEEDL=$SL tb_ape -do saif.do > sim.log 2>&1 || true
$H/../venv/bin/python $H/../flow/saif_window.py A.saif B.saif act_$T.saif > window.log 2>&1
rm -f A.saif B.saif
echo "window_ps $TS $TE period_ps $PER cycles $(( (TE-TS)/PER ))" > window_info.txt
$H/../venv/bin/python $H/tb/compare.py . > compare.log 2>&1 || true
grep -E "SUMMARY|PASS|FAIL" compare.log | head -4; cat window.log | tail -2
