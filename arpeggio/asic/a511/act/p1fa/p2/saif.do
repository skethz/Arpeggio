power add -in -out -inout -internal -r /tb_ape/dut/*
run 132250ps
power report -all -bsaif A.saif
run 926501000ps
power report -all -bsaif B.saif
run -all
quit -f
