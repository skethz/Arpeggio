#!/usr/bin/env bash
# A5.9 (PROTOCOL_A59.md): RTL cycles of first-accept SA and Antiphase at A = 1 and 4, hostB CPU only (nice 19). All files stay under rtl_a59/.
# Stage capture: P2 stimulus on GPU1 (UUID-checked); stage sim: builds, references, simulations, checks; stage analyze.
set -u
R59=<SCRATCH>/ap_ber_20261024/rtl_a59; cd $R59
export CCACHE_DISABLE=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=$R59/tmp OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p tmp build runs logs
V="verilator verilator"
W="--cc --exe --build -j 4 -O3 --x-assign 0 --x-initial 0 -Wno-fatal -Wno-WIDTH -Wno-UNSIGNED -Wno-CMPCONST -Wno-UNOPTFLAT -Wno-LATCH --top-module tb_fa"
stage=${1:-all}
if [ "$stage" = capture ] || [ "$stage" = all ]; then
  ( export MIMO_GPU_UUID=<GPU_UUID>; source ../env_hostb_a56.sh >/dev/null && cd $R59 && \
    export PYTHONPATH=$R59/src:<SCRATCH>/ap_ber_20261024/src:<SCRATCH>/ap_ber_20261024/code_mimo/src && \
    nice -n 19 python src/capture_a59.py $R59/capture_p2_9600.pt ) > logs/capture_p2.log 2>&1 || { echo "CAPTURE FAILED"; exit 1; }
  tail -n 2 logs/capture_p2.log
fi
source ../venv/bin/activate
export CUDA_VISIBLE_DEVICES= PYTHONPATH=$R59/src:<SCRATCH>/ap_ber_20261024/src:<SCRATCH>/ap_ber_20261024/code_mimo/src
bld() { # name A D engine
  local n=$1 A=$2 D=$3 E=$4
  ( cd build; rm -rf $n; nice -n 19 $V $W -CFLAGS -O2 -DAPE_PHILOX -GA=$A -GD=$D -Mdir $n ../src/$E ../src/ape_mem_behav.sv ../src/tb_fa59.sv ../src/sim_main.cpp > build_$n.log 2>&1 ) || echo "BUILD FAILED $n"
}
run() { # stim binary A
  local d=runs/$1_$2; rm -rf $d; mkdir -p $d; cp runs/stim_$1/stim.txt runs/stim_$1/ref.json $d/
  ( cd $d; nice -n 19 ../../build/$2/Vtb_fa | tail -n 1 ); nice -n 19 python src/fa_ref59.py check $d $3; echo "exit $? : $1 $2"
}
if [ "$stage" = sim ] || [ "$stage" = all ]; then
  # references (R = Ns: 32 at P1, 8 at P2), four in parallel
  A59_R=32 nice -n 19 python src/fa_ref59.py gen runs/stim_p1fa capture_9600.pt 64 0.1 0.1 0.0 rand fa  > logs/gen_p1fa.log 2>&1 &
  A59_R=32 nice -n 19 python src/fa_ref59.py gen runs/stim_p1ap capture_9600.pt 128 0.3 0.3 0.4 rand par > logs/gen_p1ap.log 2>&1 &
  A59_R=8 nice -n 19 python src/fa_ref59.py gen runs/stim_p2fa capture_p2_9600.pt 32 0.1 0.1 0.0 rand fa > logs/gen_p2fa.log 2>&1 &
  A59_R=8 nice -n 19 python src/fa_ref59.py gen runs/stim_p2ap capture_p2_9600.pt 128 0.3 0.3 0.4 rand par > logs/gen_p2ap.log 2>&1 &
  for A in 1 4; do for Dl in 32 64; do
    bld fa_a${A}_d$Dl $A $Dl ape_engine_fa.sv & b1=$!; bld v14_a${A}_d$Dl $A $Dl ape_engine.sv & b2=$!; wait $b1 $b2
  done; done
  wait
  cat logs/gen_*.log
  {
  for A in 1 4; do
    run p1fa fa_a${A}_d32 $A & run p1ap v14_a${A}_d32 $A & run p2fa fa_a${A}_d64 $A & run p2ap v14_a${A}_d64 $A & wait
  done
  } 2>&1 | tee RESULT.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|cycles |Traceback|Error'
fi
if [ "$stage" = analyze ] || [ "$stage" = all ]; then
  nice -n 19 python src/analyze_a59.py $R59/runs $R59/A59.json
fi
