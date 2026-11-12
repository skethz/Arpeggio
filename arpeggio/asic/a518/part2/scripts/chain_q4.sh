#!/bin/bash
# A5.18 part 2 W2/W3 Q4 (PROTOCOL_A518_part2.md 0d0eeeee): Chord D128 on the x64ap stimulus.
# SAIF (hostB) -> Genus TCF on v14_d128_p1000/out/opt.db (only on hostE, where the Table IV X64 TCF was made) -> Innovus TT
# power on ape_d128_p1200_r4 (hostC) at 1.20 ns, with Table IV's X64_TT.tcf in the same session as a control (259.52 mW).
set -u
R=<SCRATCH>/antiphase_asic_20261017; P=$R/a518/part2; L=$R/a518/RUNLOG.txt; S=$P/scripts
SA=$P/act/x64ap/p2/act_x64ap.saif
until grep -q "end act x64ap" $L && [ -s $SA ]; do sleep 60; done
ssh -n -o BatchMode=yes <USER>@hostE "mkdir -p $P/act $P/tcf $S"
scp -q $SA $S/pick_cpus.sh $S/tcf_remote.sh <USER>@hostE:$P/act/ < /dev/null
ssh -n -o BatchMode=yes <USER>@hostE "mv $P/act/pick_cpus.sh $P/act/tcf_remote.sh $S/"
echo "$(date -u +%FT%TZ) start tcf x64ap hostE saif $(sha256sum $SA | cut -c1-12)" >> $L
o=$(ssh -n -o BatchMode=yes <USER>@hostE "bash $S/tcf_remote.sh $R/ape/syn/v14_d128_p1000/out/opt.db $P/act/act_x64ap.saif $P/tcf/x64ap_1000")
echo "$(date -u +%FT%TZ) end tcf x64ap hostE $o" >> $L
ssh -n -o BatchMode=yes <USER>@hostE "scp -q $P/tcf/x64ap_1000_netlist.tcf <USER>@hostC:$P/power/tcf/"
scp -q $S/pick_cpus.sh $S/power_remote.sh <USER>@hostC:$S/ < /dev/null
echo "$(date -u +%FT%TZ) launch power Q4 hostC" >> $L
ssh -n -o BatchMode=yes <USER>@hostC "bash $S/power_remote.sh Q4 $R/flow_v2_20261024/ape_d128_p1200_r4/db/final.enc.dat ape_engine_D128_A4_SEEDL4 1200 x64ap=$P/power/tcf/x64ap_1000_netlist.tcf X64=$R/ape/tcf/X64_TT.tcf"
echo "$(date -u +%FT%TZ) Q4 done: $(ssh -n -o BatchMode=yes <USER>@hostC "grep Q4 $R/a518/RUNLOG_hostc.txt" | tail -3 | cut -c1-120 | paste -sd'|')" >> $L
