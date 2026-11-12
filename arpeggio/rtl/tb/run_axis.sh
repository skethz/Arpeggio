#!/bin/bash
# usage: run_axis.sh <vector dir> <D> <A> <SEEDL> <GAP_PCT> <BP_PCT> <tag>   (production build; run from ape/)
set -e
V=$1; D=$2; A=$3; SL=$4; G=$5; B=$6; T=$7; H=$(pwd)
W=$V/axis_$T; rm -rf $W; mkdir -p $W; cd $W; cp ../stim.txt ../expected.json .
questa-2025.3 vlib work > vlog.log 2>&1
questa-2025.3 vlog -sv $H/rtl/ape_mem_behav.sv $H/rtl/ape_engine.sv $H/rtl/ape_axis.v $H/tb/tb_ape_axis.sv >> vlog.log 2>&1 || { tail -20 vlog.log; exit 2; }
questa-2025.3 vsim -c -GD=$D -GA=$A -GSEEDL=$SL -GGAP_PCT=$G -GBP_PCT=$B tb_ape_axis -do "run -all; quit -f" > sim.log 2>&1 || true
grep -E "TB_|Error|Fatal" sim.log | head -3
$H/../venv/bin/python $H/tb/compare_axis.py . | tee compare.log
