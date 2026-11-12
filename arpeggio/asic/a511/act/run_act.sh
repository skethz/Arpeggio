#!/bin/bash
# A5.11 activity run (PROTOCOL_A511 §4 + A1/A2): production build, 1000 ps; pass 1 window, pass 2 windowed SAIF.
# usage: run_act.sh <tag> <engine file> <D> <SEEDL> <stim dir>
set -u
R=<SCRATCH>/antiphase_asic_20261017; O=$R/fa_a511; T=$1; E=$2; D=$3; SL=$4; ST=$5; PER=1000
export HOME=$R/home XDG_CONFIG_HOME=$R/home/.config TMPDIR=$R/tmp
W=$O/act/$T; rm -rf $W; mkdir -p $W/p1 $W/p2; cp $ST/stim.txt $W/p1/; cp $ST/stim.txt $W/p2/
sha256sum $ST/stim.txt $R/ape/rtl/$E $R/ape/tb/tb_ape.sv > $W/inputs.sha256
echo "$(date -u +%FT%TZ) start act $T" >> $O/RUNLOG.txt
cd $W/p1
questa-2025.3 vlib work > vlog.log 2>&1
questa-2025.3 vlog -sv +define+CLK_HALF_NS=0.5 $R/ape/rtl/ape_mem_behav.sv $R/ape/rtl/$E $R/ape/tb/tb_ape.sv >> vlog.log 2>&1
questa-2025.3 vsim -c -GD=$D -GA=4 -GSEEDL=$SL tb_ape -do "run -all; quit -f" > sim.log 2>&1
F=$(python3 -c "
ops=[int(l.split()[0]) for l in open('stim.txt') if l.strip()]; print(next(i for i,o in enumerate(ops) if o!=3))")
ACC=$(awk -v f=$F '$1=="A" && $2==f {print $3}' rtl_out.txt); EC=$(awk '$1=="E"{print $2}' rtl_out.txt)
NB=$(grep -c '^B ' rtl_out.txt); NA=$(grep -c '^A ' rtl_out.txt); NC=$(grep -c . stim.txt)
CYC=$((EC - 5)); TS=$(python3 -c "print(int(round((4.5 + $ACC - 0.25) * $PER)))"); TE=$(python3 -c "print(int(round((4.5 + $CYC - 0.25) * $PER)))")
echo "first_work_cmd $F acc $ACC cycles $CYC E $EC beats $NB accepted $NA of $NC window_ps $TS $TE window_cycles $((CYC - ACC))" > ../pass1.txt
[ "$NA" = "$NC" ] && [ -n "$EC" ] || { echo "PASS1_FAIL" >> ../pass1.txt; echo "$(date -u +%FT%TZ) act $T PASS1_FAIL" >> $O/RUNLOG.txt; exit 1; }
cd $W/p2
questa-2025.3 vlib work > vlog.log 2>&1
questa-2025.3 vlog -sv +define+CLK_HALF_NS=0.5 $R/ape/rtl/ape_mem_behav.sv $R/ape/rtl/$E $R/ape/tb/tb_ape.sv >> vlog.log 2>&1
cat > saif.do <<EOD
power add -in -out -inout -internal -r /tb_ape/dut/*
run ${TS}ps
power report -all -bsaif A.saif
run $((TE-TS))ps
power report -all -bsaif B.saif
run -all
quit -f
EOD
questa-2025.3 vsim -c -voptargs=+acc -GD=$D -GA=4 -GSEEDL=$SL tb_ape -do saif.do > sim.log 2>&1
python3 $R/flow/saif_window.py A.saif B.saif act_$T.saif > window.log 2>&1; rm -f A.saif B.saif
cmp -s $W/p1/rtl_out.txt $W/p2/rtl_out.txt && echo "p2 rtl_out identical to p1" >> ../pass1.txt || echo "p2 rtl_out DIFFERS" >> ../pass1.txt
echo "$(date -u +%FT%TZ) end act $T $(tail -1 window.log)" >> $O/RUNLOG.txt
