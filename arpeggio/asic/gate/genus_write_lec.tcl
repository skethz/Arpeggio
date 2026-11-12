# Writes Genus' composite LEC dofile (RTL -> fv_map -> netlist) from the restored synthesis database. read_db only:
# no mapping, optimisation or netlist writing (PROTOCOL.md §3.1). Environment: L_DB (opt.db copy), L_NETLIST (the
# synthesis netlist the layout read), L_WORK (dir holding the copied fv/ verification directory).
set_db max_cpus_per_server 2
cd $::env(L_WORK)
read_db $::env(L_DB)
puts "GENUS_VERIF_DIR [get_db verification_directory]"
puts "GENUS_TOP [get_db [lindex [get_db designs] 0] .name]"
catch {help write_do_lec}
set rc [catch {write_do_lec -revised_design $::env(L_NETLIST) -logfile $::env(L_WORK)/lec.log > $::env(L_WORK)/lec_genus.do} e]
puts "GENUS_WRITE_DO_LEC rc=$rc $e"
puts GENUS_LEC_DONE
exit 0
