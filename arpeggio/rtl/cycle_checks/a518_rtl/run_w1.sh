#!/usr/bin/env bash
# A5.18 part 2: run_rtl_a59.sh's sim stage at D = 128, A = 4, CPU only, CPUs 0-23, nice 19.
set -u
A=<SCRATCH>/arpeggio_ber_20261024; W=$A/a518_rtl; cd $W
export CCACHE_DISABLE=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=$W/tmp OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
V="verilator verilator"
WF="--cc --exe --build -j 4 -O3 --x-assign 0 --x-initial 0 -Wno-fatal -Wno-WIDTH -Wno-UNSIGNED -Wno-CMPCONST -Wno-UNOPTFLAT -Wno-LATCH --unroll-count 1024 --top-module tb_arpeggio"   # --unroll-count: D = 128 loops exceed the default 64 (BLKLOOPINIT)
source $A/venv/bin/activate
export CUDA_VISIBLE_DEVICES= PYTHONPATH=$W/src:$A/src:$A/code_mimo/src
L=<SCRATCH>/arpeggio_asic_20261017/a518/RUNLOG.txt
bld() { # name engine extra-defines
  ( cd build; rm -rf $1; taskset -c 0-23 nice -n 19 $V $WF -CFLAGS -O2 -DENGINE_PHILOX $3 -GA=4 -GD=128 -Mdir $1 ../src/$2 ../src/engine_mem_behav.sv ../src/tb_arpeggio59.sv ../src/sim_main.cpp > build_$1.log 2>&1 ) || echo "BUILD FAILED $1"
}
run() { # stim binary
  local d=runs/$1_$2; rm -rf $d; mkdir -p $d; cp runs/stim_$1/stim.txt runs/stim_$1/ref.json $d/
  ( cd $d; taskset -c 0-23 nice -n 19 ../../build/$2/Vtb_arpeggio | tail -n 1 ); taskset -c 0-23 nice -n 19 python src/arpeggio_ref59.py check $d 4; echo "exit $? : $1 $2"
}
stage=${1:-all}
if [ "$stage" = main ] || [ "$stage" = all ]; then
  echo "$(date -u +%FT%TZ) W1 gen/build/run start" >> $L
  A59_R=8 taskset -c 0-23 nice -n 19 python src/arpeggio_ref59.py gen runs/stim_x64arpeggio capture_x64_9600.pt 64 0.1 0.1 0.0 bal arpeggio > logs/gen_x64arpeggio.log 2>&1 &
  A59_R=8 taskset -c 0-23 nice -n 19 python src/arpeggio_ref59.py gen runs/stim_x64chord capture_x64_9600.pt 128 0.3 0.3 0.4 rand par > logs/gen_x64chord.log 2>&1 &
  bld arpeggio_bal_a4_d128 arpeggio_engine.sv -DENGINE_ARPEGGIO_BAL & b1=$!; bld v14_a4_d128 chord_engine.sv "" & b2=$!; wait $b1 $b2
  wait
  cat logs/gen_x64*.log
  { run x64arpeggio arpeggio_bal_a4_d128 & run x64chord v14_a4_d128 & wait; } 2>&1 | tee RESULT_main.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|cycles |Traceback|Error'
  python src/analyze_a518w1.py runs x64arpeggio_arpeggio_bal_a4_d128 x64chord_v14_a4_d128 W1_bal.json | tee -a RESULT_main.txt
  echo "$(date -u +%FT%TZ) W1 main done: $(tail -1 RESULT_main.txt | cut -c1-160)" >> $L
fi
if [ "$stage" = buildrun ]; then   # gens kept, builds and runs only
  echo "$(date -u +%FT%TZ) W1 buildrun start (--unroll-count 1024)" >> $L
  bld arpeggio_bal_a4_d128 arpeggio_engine.sv -DENGINE_ARPEGGIO_BAL & b1=$!; bld v14_a4_d128 chord_engine.sv "" & b2=$!; wait $b1 $b2
  while pgrep -u <USER> -f "gen runs/stim_x64chord" > /dev/null || [ ! -s runs/stim_x64chord/ref.json ]; do sleep 20; done
  { run x64arpeggio arpeggio_bal_a4_d128 & run x64chord v14_a4_d128 & wait; } 2>&1 | tee RESULT_main.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|cycles |Traceback|Error'
  python src/analyze_a518w1.py runs x64arpeggio_arpeggio_bal_a4_d128 x64chord_v14_a4_d128 W1_bal.json | tee -a RESULT_main.txt
  echo "$(date -u +%FT%TZ) W1 buildrun done: $(tail -1 RESULT_main.txt | cut -c1-160)" >> $L
fi
if [ "$stage" = randfallback ]; then   # random-start build, only if the balanced-start check fails
  A59_R=8 taskset -c 0-23 nice -n 19 python src/arpeggio_ref59.py gen runs/stim_x64arpeggior capture_x64_9600.pt 64 0.1 0.1 0.0 rand arpeggio > logs/gen_x64arpeggior.log 2>&1
  bld arpeggio_a4_d128 arpeggio_engine.sv ""
  run x64arpeggior arpeggio_a4_d128 2>&1 | tee RESULT_rand.txt
  python src/analyze_a518w1.py runs x64arpeggior_arpeggio_a4_d128 x64chord_v14_a4_d128 W1_rand.json | tee -a RESULT_rand.txt
fi
