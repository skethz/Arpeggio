power add -in -out -inout -internal -r /tb_ape/dut/*
run 260250ps
power report -all -bsaif A.saif
run 341651000ps
power report -all -bsaif B.saif
run -all
quit -f
