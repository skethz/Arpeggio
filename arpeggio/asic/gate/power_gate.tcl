# Innovus post-route TT power of a saved routed engine with netlist TCFs (gate_r4, PROTOCOL.md §4). Analysis only: the
# database (a sha256-verified copy of the accepted run) is restored into this session; nothing is optimised or saved.
# Template: an earlier project power script. Environment: PP_DB, PP_TOP, PP_OUT, PP_CPUS, PP_TCFS ("tag=/path/a.tcf tag2=/path/b.tcf")
setMultiCpuUsage -localCpu $::env(PP_CPUS)
set OUT $::env(PP_OUT)
proc step {name script} {
  set f [open $::OUT/${name}_started.txt w]; puts $f [clock seconds]; close $f
  set rc [catch {uplevel 1 $script} message options]
  set f [open $::OUT/${name}_status.txt w]; puts $f $rc; close $f
  if {$rc} {
    set f [open $::OUT/${name}_error_private.txt w]; puts $f $message; puts $f $options; close $f
    puts "POWER_GATE_STAGE_FAILED $name"; exit 1
  }
  puts "POWER_GATE_STAGE_DONE $name"
}
step restore {restoreDesign $::env(PP_DB) $::env(PP_TOP)}
set fp_before [list [dbGet top.insts.name] [dbGet top.insts.cell.name] [dbGet top.insts.pt] [dbGet top.insts.orient] [dbGet top.nets.name] [dbGet top.fPlan.box]]
write_sdc $OUT/constraints_private.sdc
step views {set_analysis_view -setup [list view_tt] -hold [list view_tt]}
setExtractRCMode -engine postRoute
setAnalysisMode -analysisType onChipVariation -cppr both
step extract {extractRC}
set f [open $OUT/insts_private.tsv w]
foreach inst [dbGet top.insts] {
  set outs {}
  foreach it [dbGet -e $inst.instTerms] { if {[dbGet $it.isOutput] == 1} { set n [dbGet $it.net.name]; if {$n ne "0x0"} {lappend outs $n} } }
  puts $f "[dbGet $inst.name]\t[dbGet $inst.cell.isSequential]\t[dbGet $inst.isPhysOnly]\t[dbGet $inst.cell.baseClass]\t[join $outs { }]"
}
close $f
foreach kv $::env(PP_TCFS) {
  set p [split $kv =]; set tag [lindex $p 0]; set tcf [lindex $p 1]
  set D $OUT/$tag; file mkdir $D
  step ${tag}_pmode {set_power_analysis_mode -reset; set_power_analysis_mode -method static -analysis_view view_tt -write_static_currents false -create_binary_db false}
  step ${tag}_act_reset {read_activity_file -reset}
  step ${tag}_act_read {read_activity_file -format TCF -scope $::env(PP_TOP) $tcf}
  catch {get_activity -summary -outfile $D/activity_before_private.rpt}
  step ${tag}_power_out {set_power_output_dir $D/power_tt}
  step ${tag}_power_tt {report_power -view view_tt -power_unit mW -outfile $D/power_tt.rpt}
  step ${tag}_after_summary {get_activity -summary -outfile $D/activity_after_private.rpt}
  foreach role {activity_file set_switching_activity propagated default} {
    step ${tag}_source_$role {get_activity -list_of_nets_based_on_source_of_activity_info $role -outfile $D/source_${role}_private.rpt}
  }
  foreach role {primary_inputs sequential combinational memory ICG black_box} {
    step ${tag}_driver_$role {get_activity -list_of_nets_based_on_driver $role -outfile $D/driver_${role}_private.rpt}
  }
  step ${tag}_insts_power {report_power -view view_tt -instances * -power_unit mW -outfile $D/insts_power_tt_private.rpt}
  step ${tag}_clock_power {report_power -view view_tt -clock_network all -power_unit mW -outfile $D/clock_power_tt_private.rpt}
  puts "POWER_GATE_TCF_DONE $tag"
}
set fp_after [list [dbGet top.insts.name] [dbGet top.insts.cell.name] [dbGet top.insts.pt] [dbGet top.insts.orient] [dbGet top.nets.name] [dbGet top.fPlan.box]]
set f [open $OUT/invariant_public.txt w]
puts $f "instance_placement_net_footprint_unchanged [expr {$fp_before eq $fp_after}]"
puts $f "insts [llength [dbGet top.insts]] nets [llength [dbGet top.nets]]"
close $f
if {$fp_before ne $fp_after} {puts "POWER_GATE_FINGERPRINT_CHANGED"; exit 1}
puts "POWER_GATE_DONE"
exit 0
