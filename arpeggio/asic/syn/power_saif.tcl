# Genus power with simulation activity (SAIF) on a synthesized design. SERVER ONLY.
# Environment: PW_DB (opt.db), PW_SAIF (SAIF file), PW_SCOPE (instance path of the design in the SAIF, e.g. tb/dut),
#              PW_SCALE (simulated clock period / synthesized period), PW_OUT (report prefix).
set_db max_cpus_per_server 4
read_db $::env(PW_DB)
report_power > $::env(PW_OUT)_vectorless.rpt
# the joules power engine refuses -scale: SAIFs are simulated at the layout period and read unscaled (PW_SCALE 1)
if {$::env(PW_SCALE) != 1} { puts "PW_ERROR scale $::env(PW_SCALE) not supported; simulate at the layout period"; exit 1 }
read_saif -instance $::env(PW_SCOPE) -verbose $::env(PW_SAIF)
report_power > $::env(PW_OUT)_saif.rpt
report_power -by_hierarchy -levels 3 > $::env(PW_OUT)_saif_hier.rpt
catch {report_power -by_category > $::env(PW_OUT)_saif_bycat.rpt}
# netlist-level activity for Innovus (asserted + computed, hierarchical); Innovus rejects the empty top scope Genus
# writes, so the top instance name is filled in
if {[catch {write_tcf -computed -hierarchical > $::env(PW_OUT)_netlist_raw.tcf} e]} { puts "write_tcf failed: $e" }
set top [get_db [lindex [get_db designs] 0] .name]
if {[file exists $::env(PW_OUT)_netlist_raw.tcf]} {
    set fi [open $::env(PW_OUT)_netlist_raw.tcf r]; set txt [read $fi]; close $fi
    set i [string first {instance("")} $txt]
    if {$i >= 0} { set txt [string replace $txt $i [expr {$i + 11}] "instance(\"$top\")"] }
    set fo [open $::env(PW_OUT)_netlist.tcf w]; puts -nonewline $fo $txt; close $fo
    puts "PW_TCF $::env(PW_OUT)_netlist.tcf top=$top"
}
puts "PW_DONE"
exit
