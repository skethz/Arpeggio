#!/usr/bin/env bash
# A5.10: fused first-accept RTL cycles at A = 1, 4, 6, 8 against Chord and first-accept; hostB CPU only (nice 19).
# Stages: setup (sources, hashes), gen (references; must equal A5.9's stimuli), build, sim (runs + checks + negative controls), analyze, recost.
set -u
R=<SCRATCH>/arpeggio_ber_20261024/rtl_a510; cd $R
export CCACHE_DISABLE=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=$R/tmp OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p tmp build runs logs
V="verilator verilator"
W="--cc --exe --build -j 4 -O3 --x-assign 0 --x-initial 0 -Wno-fatal -Wno-WIDTH -Wno-UNSIGNED -Wno-CMPCONST -Wno-UNOPTFLAT -Wno-LATCH --top-module tb_arpeggio"
stage=${1:-all}
source ../venv/bin/activate
export CUDA_VISIBLE_DEVICES= PYTHONPATH=$R/src:<SCRATCH>/arpeggio_ber_20261024/src:<SCRATCH>/arpeggio_ber_20261024/code_mimo/src
if [ "$stage" = gen ] || [ "$stage" = all ]; then
  A59_R=32 nice -n 19 python src/fx_ref510.py gen runs/stim_p1arpeggio ../rtl_a55/capture_9600.pt 64 0.1 0.1 0.0 rand arpeggio  > logs/gen_p1arpeggio.log 2>&1 &
  A59_R=32 nice -n 19 python src/fx_ref510.py gen runs/stim_p1chord ../rtl_a55/capture_9600.pt 128 0.3 0.3 0.4 rand par > logs/gen_p1chord.log 2>&1 &
  A59_R=8 nice -n 19 python src/fx_ref510.py gen runs/stim_p2arpeggio ../rtl_a59/capture_p2_9600.pt 32 0.1 0.1 0.0 rand arpeggio > logs/gen_p2arpeggio.log 2>&1 &
  A59_R=8 nice -n 19 python src/fx_ref510.py gen runs/stim_p2chord ../rtl_a59/capture_p2_9600.pt 128 0.3 0.3 0.4 rand par > logs/gen_p2chord.log 2>&1 &
  wait; cat logs/gen_*.log
  for s in p1arpeggio p1chord p2arpeggio p2chord; do for f in stim.txt ref.json; do
    if cmp -s runs/stim_$s/$f ../rtl_a59/runs/stim_$s/$f; then echo "SAME AS A5.9 $s/$f"; else echo "DIFFERS FROM A5.9 $s/$f"; fi
  done; done
fi
bld() { # name A D engine defines...
  local n=$1 A=$2 D=$3 E=$4; shift 4
  ( cd build; rm -rf $n; nice -n 19 $V $W -CFLAGS -O2 -DENGINE_PHILOX "$@" -GA=$A -GD=$D -Mdir $n ../src/$E ../src/engine_mem_behav.sv ../src/tb_arpeggio59.sv ../src/sim_main.cpp > build_$n.log 2>&1 ) || echo "BUILD FAILED $n"
}
if [ "$stage" = build ] || [ "$stage" = all ]; then
  for A in 1 4 6 8; do for Dl in 32 64; do
    bld v14_a${A}_d$Dl $A $Dl chord_engine.sv & b1=$!; bld arpeggio_a${A}_d$Dl $A $Dl arpeggio_engine.sv & b2=$!; wait $b1 $b2
    bld fx2_a${A}_d$Dl $A $Dl chord_engine_fx.sv -DENGINE_FX_CHECK & b1=$!; bld fx3_a${A}_d$Dl $A $Dl chord_engine_fx.sv -DENGINE_FX_CHECK -DENGINE_FX3 & b2=$!; wait $b1 $b2
  done; done
  bld fx2nm_a1_d32 1 32 chord_engine_fx.sv -DENGINE_FX_CHECK -DFX_BUG_NOMASK & b1=$!; bld fx2st_a1_d32 1 32 chord_engine_fx.sv -DENGINE_FX_CHECK -DFX_BUG_STALE & b2=$!; wait $b1 $b2
  ls build | grep -c _a; grep -l -i "error" build/build_*.log || true
fi
run() { # stim binary A eng
  local d=runs/$1_$2; rm -rf $d; mkdir -p $d; cp runs/stim_$1/stim.txt runs/stim_$1/ref.json $d/
  ( cd $d; nice -n 19 ../../build/$2/Vtb_arpeggio > tb.txt 2>&1; tail -n 1 tb.txt ); nice -n 19 python src/fx_ref510.py check $d $3 $4; echo "exit $? : $1 $2"
}
if [ "$stage" = sim ] || [ "$stage" = all ]; then
  {
  for A in 1 4 6 8; do
    run p1chord v14_a${A}_d32 $A v14 & run p1arpeggio arpeggio_a${A}_d32 $A arpeggio & run p1arpeggio fx2_a${A}_d32 $A fx2 & run p1arpeggio fx3_a${A}_d32 $A fx3 & wait
    run p2chord v14_a${A}_d64 $A v14 & run p2arpeggio arpeggio_a${A}_d64 $A arpeggio & run p2arpeggio fx2_a${A}_d64 $A fx2 & run p2arpeggio fx3_a${A}_d64 $A fx3 & wait
  done
  } 2>&1 | tee RESULT.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|cycles |Traceback|Error|FXCHECK|TB_CAP'
  : > logs/neg.txt
  for n in fx2nm fx2st; do
    d=runs/p1arpeggio_${n}_a1_d32; rm -rf $d; mkdir -p $d; cp runs/stim_p1arpeggio/stim.txt runs/stim_p1arpeggio/ref.json $d/
    tb=$( cd $d; TB_CAP=30000000 nice -n 19 ../../build/${n}_a1_d32/Vtb_arpeggio 2>&1 | tail -n 1 | awk '{print $1}' )
    nice -n 19 python src/fx_ref510.py check $d 1 fx2 > $d/check.txt 2>&1; ce=$?
    echo "NEG $n check_exit=$ce tb=$tb" | tee -a logs/neg.txt; grep -E "FAIL|PASS" $d/check.txt | head -n 8
  done
fi
if [ "$stage" = analyze ] || [ "$stage" = all ]; then
  nice -n 19 python src/analyze_a510.py $R/runs $R/logs/neg.txt $R/A510.json
fi
if [ "$stage" = recost ] || [ "$stage" = all ]; then
  nice -n 19 python src/recost_a510.py <SCRATCH>/arpeggio_ber_20261024/results/a55 <SCRATCH>/arpeggio_ber_20261024/results/tuned_a52.json $R/recost_a510.json
fi
