power add -in -out -inout -internal -r /tb_ape/dut/*
run 68250ps
power report -all -bsaif A.saif
run 246913000ps
power report -all -bsaif B.saif
run -all
quit -f
