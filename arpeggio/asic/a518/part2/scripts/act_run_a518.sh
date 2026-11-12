#!/bin/bash
# A5.18 part 2 W2 (PROTOCOL_A518_part2.md 0d0eeeee): A5.11 section 4 activity with A1/A2 at D = 128.
# Pass 1 (no SAIF) sets TS (acceptance of the first command with op != 3) and TE (E line - 5 idle cycles), pass 2 writes the
# windowed SAIF over [TS, TE] at 1000 ps (A1) with run_saif.sh's power commands and flow/saif_window.py.
# usage: act_run_a518.sh <tag> <engine .sv> <stim dir> <D> <SEEDL> [vlog defines]
set -u
R=<SCRATCH>/antiphase_asic_20261017; P=$R/a518/part2; PY=python3
t=$1; E=$2; S=$3; D=$4; SL=$5; DEF=${6:-}
W=$P/act/$t; rm -rf $W; mkdir -p $W/p1 $W/p2
sha256sum $S/stim.txt $E $R/ape/tb/tb_ape.sv $R/ape/rtl/ape_mem_behav.sv > $W/inputs.sha256
echo "$(date -u +%FT%TZ) start act $t ($(basename $E) D=$D SEEDL=$SL $DEF stim $(sha256sum $S/stim.txt | cut -c1-12))" >> $R/a518/RUNLOG.txt
comp() { cp $S/stim.txt .; questa-2025.3 vlib work > vlog.log 2>&1
  questa-2025.3 vlog -sv +define+CLK_HALF_NS=0.5 $DEF $R/ape/rtl/ape_mem_behav.sv $E $R/ape/tb/tb_ape.sv >> vlog.log 2>&1; }
cd $W/p1 && comp && questa-2025.3 vsim -c tb_ape -do "run -all; quit -f" -GD=$D -GSEEDL=$SL -GA=4 > sim.log 2>&1
read TS TE INFO < <($PY - <<PYX
cmds = [l.split() for l in open('stim.txt') if l.strip()]
f = next(i for i, c in enumerate(cmds) if c[0] != '3')
acc, beats, E = {}, 0, None
for l in open('rtl_out.txt'):
    w = l.split()
    if w[0] == 'A': acc[int(w[1])] = int(w[2])
    elif w[0] == 'B': beats += 1
    elif w[0] == 'E': E = int(w[1])
exp = 0
for c in cmds:
    if c[0] == '4':
        v = int(c[2], 16); exp += (v & 7) * ((v >> 3) & 0xFFF)
cyc = E - 5
TS = int(round((4.5 + acc[f] - 0.25) * 1000)); TE = int(round((4.5 + cyc - 0.25) * 1000))
ok = len(acc) == len(cmds) and beats == exp
print(TS, TE, 'first_work_cmd %d acc %d cycles %d E %d beats %d expected %d accepted %d of %d window_cycles %d %s' % (f, acc[f], cyc, E, beats, exp, len(acc), len(cmds), (TE - TS) // 1000, 'OK' if ok else 'FAIL'))
PYX
)
echo "$INFO window_ps $TS $TE" > $W/pass1.txt
case "$INFO" in *OK) ;; *) echo "$(date -u +%FT%TZ) act $t pass 1 FAILED: $INFO" >> $R/a518/RUNLOG.txt; exit 1;; esac
cd $W/p2 && comp
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
$PY $R/flow/saif_window.py A.saif B.saif act_$t.saif > window.log 2>&1; rm -f A.saif B.saif
cmp -s $W/p1/rtl_out.txt rtl_out.txt && echo "p2 rtl_out identical to p1" >> $W/pass1.txt || echo "p2 rtl_out DIFFERS from p1" >> $W/pass1.txt
echo "$(date -u +%FT%TZ) end act $t $(head -1 $W/pass1.txt | cut -c1-150) | $(tail -1 $W/pass1.txt) | $(tail -1 window.log)" >> $R/a518/RUNLOG.txt
