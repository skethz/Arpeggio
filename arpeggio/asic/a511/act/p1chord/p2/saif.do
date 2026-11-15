power add -in -out -inout -internal -r /tb_engine/dut/*
run 260250ps
power report -all -bsaif A.saif
run 1095363000ps
power report -all -bsaif B.saif
run -all
quit -f
