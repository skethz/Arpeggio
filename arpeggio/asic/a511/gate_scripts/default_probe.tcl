# Diagnosis only (gate_r4): which outputs carry the default-activity nets after reading the TCF. Restore, extract, read the
# TCF, then for each default net print the driver pin name and the instance's other outputs with their activity.
# Environment: PP_DB PP_TOP PP_OUT PP_CPUS PP_TCF PP_DEFAULT_LIST
setMultiCpuUsage -localCpu $::env(PP_CPUS)
set OUT $::env(PP_OUT)
restoreDesign $::env(PP_DB) $::env(PP_TOP)
set_analysis_view -setup [list view_tt] -hold [list view_tt]
setExtractRCMode -engine postRoute
setAnalysisMode -analysisType onChipVariation -cppr both
extractRC
set_power_analysis_mode -reset
set_power_analysis_mode -method static -analysis_view view_tt -write_static_currents false -create_binary_db false
read_activity_file -reset
read_activity_file -format TCF -scope $::env(PP_TOP) $::env(PP_TCF)
set_power_output_dir $OUT/power_tt
report_power -view view_tt -power_unit mW -outfile $OUT/power_tt.rpt
set f [open $::env(PP_DEFAULT_LIST) r]; set nets [read $f]; close $f
set fo [open $OUT/default_nets_private.txt w]; set pairs [dict create]
foreach n $nets {
  set net [dbGet -p top.nets.name $n]
  set drv [dbGet -e $net.instTerms.isOutput 1 -p]
  foreach it $drv {
    set inst [dbGet $it.inst]
    set myp [dbGet $it.cellTerm.name]
    set oth {}
    foreach it2 [dbGet -e $inst.instTerms.isOutput 1 -p] { if {$it2 ne $it} { set n2 [dbGet $it2.net.name]; set a2 NA; if {$n2 ne "0x0"} {catch {set a2 [get_activity -net $n2 -tcl_list]}}; lappend oth [dbGet $it2.cellTerm.name] $n2 $a2 } }
    set a1 NA; catch {set a1 [get_activity -net $n -tcl_list]}
    set fan [llength [dbGet -e $net.instTerms.isInput 1 -p]]
    puts $fo [list net $n pin $myp act $a1 fanout $fan inst [dbGet $inst.name] others $oth]
    set k "$myp<-[lindex $oth 0]"; dict incr pairs $k
  }
}
close $fo
set f [open $OUT/default_pins_public.txt w]; puts $f [dict get $pairs]; close $f
puts DEFAULT_PROBE_DONE
exit 0
