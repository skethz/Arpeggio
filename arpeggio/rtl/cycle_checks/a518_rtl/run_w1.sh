#!/usr/bin/env bash
# A5.18 part 2 W1 (PROTOCOL_A518_part2.md 0d0eeeee): run_rtl_a59.sh's sim stage at D = 128, A = 4, CPU only, CPUs 0-23, nice 19.
set -u
A=<SCRATCH>/ap_ber_20261024; W=$A/a518_rtl; cd $W
export CCACHE_DISABLE=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=$W/tmp OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
V="verilator verilator"
WF="--cc --exe --build -j 4 -O3 --x-assign 0 --x-initial 0 -Wno-fatal -Wno-WIDTH -Wno-UNSIGNED -Wno-CMPCONST -Wno-UNOPTFLAT -Wno-LATCH --unroll-count 1024 --top-module tb_fa"   # --unroll-count: D = 128 loops exceed the default 64 (BLKLOOPINIT); deviation logged 11 Nov
source $A/venv/bin/activate
export CUDA_VISIBLE_DEVICES= PYTHONPATH=$W/src:$A/src:$A/code_mimo/src
L=<SCRATCH>/antiphase_asic_20261017/a518/RUNLOG.txt
bld() { # name engine extra-defines
  ( cd build; rm -rf $1; taskset -c 0-23 nice -n 19 $V $WF -CFLAGS -O2 -DAPE_PHILOX $3 -GA=4 -GD=128 -Mdir $1 ../src/$2 ../src/ape_mem_behav.sv ../src/tb_fa59.sv ../src/sim_main.cpp > build_$1.log 2>&1 ) || echo "BUILD FAILED $1"
}
run() { # stim binary
  local d=runs/$1_$2; rm -rf $d; mkdir -p $d; cp runs/stim_$1/stim.txt runs/stim_$1/ref.json $d/
  ( cd $d; taskset -c 0-23 nice -n 19 ../../build/$2/Vtb_fa | tail -n 1 ); taskset -c 0-23 nice -n 19 python src/fa_ref59.py check $d 4; echo "exit $? : $1 $2"
}
stage=${1:-all}
if [ "$stage" = main ] || [ "$stage" = all ]; then
  echo "$(date -u +%FT%TZ) W1 gen/build/run start" >> $L
  A59_R=8 taskset -c 0-23 nice -n 19 python src/fa_ref59.py gen runs/stim_x64fa capture_x64_9600.pt 64 0.1 0.1 0.0 bal fa > logs/gen_x64fa.log 2>&1 &
  A59_R=8 taskset -c 0-23 nice -n 19 python src/fa_ref59.py gen runs/stim_x64ap capture_x64_9600.pt 128 0.3 0.3 0.4 rand par > logs/gen_x64ap.log 2>&1 &
  bld fa_bal_a4_d128 ape_engine_fa.sv -DAPE_FA_BAL & b1=$!; bld v14_a4_d128 ape_engine.sv "" & b2=$!; wait $b1 $b2
  wait
  cat logs/gen_x64*.log
  { run x64fa fa_bal_a4_d128 & run x64ap v14_a4_d128 & wait; } 2>&1 | tee RESULT_main.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|cycles |Traceback|Error'
  python src/analyze_a518w1.py runs x64fa_fa_bal_a4_d128 x64ap_v14_a4_d128 W1_bal.json | tee -a RESULT_main.txt
  echo "$(date -u +%FT%TZ) W1 main done: $(tail -1 RESULT_main.txt | cut -c1-160)" >> $L
fi
if [ "$stage" = buildrun ]; then   # after the 11 Nov build failure: gens kept, builds and runs only
  echo "$(date -u +%FT%TZ) W1 buildrun start (--unroll-count 1024)" >> $L
  bld fa_bal_a4_d128 ape_engine_fa.sv -DAPE_FA_BAL & b1=$!; bld v14_a4_d128 ape_engine.sv "" & b2=$!; wait $b1 $b2
  while pgrep -u <USER> -f "gen runs/stim_x64ap" > /dev/null || [ ! -s runs/stim_x64ap/ref.json ]; do sleep 20; done
  { run x64fa fa_bal_a4_d128 & run x64ap v14_a4_d128 & wait; } 2>&1 | tee RESULT_main.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|cycles |Traceback|Error'
  python src/analyze_a518w1.py runs x64fa_fa_bal_a4_d128 x64ap_v14_a4_d128 W1_bal.json | tee -a RESULT_main.txt
  echo "$(date -u +%FT%TZ) W1 buildrun done: $(tail -1 RESULT_main.txt | cut -c1-160)" >> $L
fi
if [ "$stage" = randfallback ]; then   # protocol W1 fallback, only if the balanced-start check fails
  A59_R=8 taskset -c 0-23 nice -n 19 python src/fa_ref59.py gen runs/stim_x64far capture_x64_9600.pt 64 0.1 0.1 0.0 rand fa > logs/gen_x64far.log 2>&1
  bld fa_a4_d128 ape_engine_fa.sv ""
  run x64far fa_a4_d128 2>&1 | tee RESULT_rand.txt
  python src/analyze_a518w1.py runs x64far_fa_a4_d128 x64ap_v14_a4_d128 W1_rand.json | tee -a RESULT_rand.txt
fi
