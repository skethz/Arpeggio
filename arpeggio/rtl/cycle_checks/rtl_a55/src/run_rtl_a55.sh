#!/usr/bin/env bash
# A5.5 RTL check (PROTOCOL_A55.md section 8), hostB CPU only. All files stay under rtl_a55/. Writes RESULT.txt.
cd <SCRATCH>/ap_ber_20261024/rtl_a55; export CCACHE_DISABLE=1 CUDA_VISIBLE_DEVICES= ; source ../venv/bin/activate
export PYTHONPATH=$PWD/src:../code_mimo/src TMPDIR=$PWD/tmp PYTHONDONTWRITEBYTECODE=1; mkdir -p tmp build runs
V="verilator verilator"
W="--cc --exe --build -j 4 -O3 --x-assign 0 --x-initial 0 -Wno-fatal -Wno-WIDTH -Wno-UNSIGNED -Wno-CMPCONST -Wno-UNOPTFLAT -Wno-LATCH --top-module tb_fa"
bld() { # name A engine defines...
  local n=$1 A=$2 E=$3; shift 3
  ( cd build; rm -rf $n; $V $W -CFLAGS -O2 -DAPE_PHILOX "$@" -GA=$A -Mdir $n ../src/$E ../src/ape_mem_behav.sv ../src/tb_fa.sv ../src/sim_main.cpp > build_$n.log 2>&1 ) || echo "BUILD FAILED $n"
}
run() { # stim binary A label
  local d=runs/$1_$2; rm -rf $d; mkdir -p $d; cp runs/stim_$1/stim.txt runs/stim_$1/ref.json $d/
  ( cd $d; ../../build/$2/Vtb_fa | tail -n 1 ); python src/fa_ref.py check $d $3; echo "exit $? : $1 $2"
}
for A in 1 4; do
  bld fa_a$A $A ape_engine_fa.sv
  bld bal_a$A $A ape_engine_fa.sv -DAPE_FA_BAL
  bld v14_a$A $A ape_engine.sv
done
bld bug_a1 1 ape_engine_fa.sv -DFA_BUG_NOMASK      # negative control: no scanned-lane mask (can livelock, so TB_CAP)
bld ebug_a1 1 ape_engine_fa.sv -DAPE_BUG           # negative control: energy update with the field after the flip
python src/fa_ref.py gen runs/stim_s8r capture_9600.pt 8 1.2 0.1 0.2 rand fa
python src/fa_ref.py gen runs/stim_s32r capture_9600.pt 32 0.2 0.2 0.2 rand fa
python src/fa_ref.py gen runs/stim_s8b capture_9600.pt 8 1.2 0.1 0.2 bal fa
python src/fa_ref.py gen runs/stim_s32b capture_9600.pt 32 0.2 0.2 0.2 bal fa
python src/fa_ref.py gen runs/stim_v14 capture_9600.pt 128 0.3 0.3 0.4 rand par
{
for A in 1 4; do
  run s8r fa_a$A $A; run s32r fa_a$A $A; run s8b bal_a$A $A; run s32b bal_a$A $A; run v14 v14_a$A $A
done
echo "=== negative controls: each must end FAILED"; export TB_CAP=2000000; run s8r bug_a1 1; run s8r ebug_a1 1
} 2>&1 | tee RESULT.txt | grep -E 'ALL PASS|FAILED|FAIL |exit|negative|Traceback|Error'
