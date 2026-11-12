#!/bin/bash
# usage: run_sim.sh <vector dir> <D> <A> <SEEDL> <philox|xs> <rtl: engine|stub|bug> [extra vlog defines]
# Questa RTL simulation of tb_ape on <vector dir>/stim.txt, then tb/compare.py. Run from the ape/ directory.
set -e
V=$1; D=$2; A=$3; SL=$4; MODE=$5; KIND=$6; shift 6
H=$(pwd)
DEF=""; [ "$MODE" = philox ] && DEF="+define+APE_PHILOX"
[ "$KIND" = bug ] && DEF="$DEF +define+APE_BUG"
SRC="$H/rtl/ape_engine.sv"; [ "$KIND" = stub ] && SRC="$H/tb/ape_stub.sv"
W=$V/sim_${KIND}; rm -rf $W; mkdir -p $W; cd $W
cp ../stim.txt ../expected.json .
questa-2025.3 vlib work > vlog.log 2>&1
questa-2025.3 vlog -sv $DEF "$@" $H/rtl/ape_mem_behav.sv $SRC $H/tb/tb_ape.sv >> vlog.log 2>&1 || { tail -30 vlog.log; exit 2; }
questa-2025.3 vsim -c -voptargs=+acc=npr -GD=$D -GA=$A -GSEEDL=$SL tb_ape -do "run -all; quit -f" > sim.log 2>&1 || true
grep -E "TB_|Error|Fatal" sim.log | head -5
$H/../venv/bin/python $H/tb/compare.py . | tee compare.log
