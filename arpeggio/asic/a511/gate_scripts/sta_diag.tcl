# Diagnosis of the failed TT control (gate_r4 sta/d32_fail1). Analysis only. Which factor moves the I/O-group slack:
# the constraint file (base vs saved mode SDC), the latency file, or creating the SS corner objects?
# Environment: CL_DB CL_TOP PNR_OUT STA_SDC_BASE STA_CPUS STA_MMMC STA_MACROS
setMultiCpuUsage -localCpu $::env(STA_CPUS)
set OUT $::env(PNR_OUT)
proc pub {text} {set f [open $::OUT/diag_public.txt a]; puts $f $text; close $f}
proc wns_groups {report} {
  set f [open $report r]; set t [read $f]; close $f
  set hdr {}
  foreach line [split $t "\n"] {
    if {[regexp {^\|\s+(Setup|Hold) mode\s+\|(.*)\|\s*$} $line all m rest]} {set hdr [lmap x [split $rest |] {string trim $x}]}
    if {$hdr ne {} && [regexp {^\|\s+WNS \(ns\):\|(.*)\|\s*$} $line all rest]} {
      set res {}; foreach h $hdr v [lmap x [split $rest |] {string trim $x}] {if {$h ne ""} {lappend res $h $v}}; return $res
    }
  }
  return NA
}
proc tv {name} {
  set_analysis_view -setup [list $name] -hold [list $name]
  timeDesign -postRoute -outDir $::OUT/reports/$name > $::OUT/${name}_setup_summary.rpt
  pub "$name [wns_groups $::OUT/${name}_setup_summary.rpt]"
}
restoreDesign $::env(CL_DB) $::env(CL_TOP)
set DBD $::env(CL_DB)
setExtractRCMode -engine postRoute
setAnalysisMode -analysisType onChipVariation -cppr both
catch {getDelayCalMode} m1; catch {getSIMode} m2; catch {getAnalysisMode} m3
set f [open $OUT/modes_private.txt w]; puts $f "$m1\n----\n$m2\n----\n$m3"; close $f
tv view_tt
set base $OUT/base_prop.sdc
file copy -force $::env(STA_SDC_BASE) $base
set f [open $base a]; puts $f "set_propagated_clock \[get_ports {clk}\]"; close $f
create_constraint_mode -name func_A -sdc_files [list $base]
create_analysis_view -name view_A -constraint_mode func_A -delay_corner dc_tt -latency_file $DBD/mmmc/views/view_tt/latency.sdc
tv view_A
create_constraint_mode -name func_D -sdc_files [list $DBD/mmmc/modes/func/func.sdc]
create_analysis_view -name view_D -constraint_mode func_D -delay_corner dc_tt -latency_file $DBD/mmmc/views/view_tt/latency.sdc
tv view_D
create_analysis_view -name view_E -constraint_mode func_D -delay_corner dc_tt
tv view_E
create_constraint_mode -name func_C -sdc_files [list $base]
create_analysis_view -name view_C -constraint_mode func_C -delay_corner dc_tt
tv view_C
# now create the SS objects exactly as sta_ss.tcl does, and re-time the saved view
set ::env(PNR_CORNER) SSG
set f [open $::env(STA_MACROS) r]; set ::env(PNR_MACROS) [string trim [read $f]]; close $f
set ::env(PNR_SDC) $base
set f [open $::env(STA_MMMC) r]; set txt [read $f]; close $f
foreach {a b} {lib_tt lib_ss rc_nom rc_ss dc_tt dc_ss view_tt view_ssinit} {regsub -all "\\m$a\\M" $txt $b txt}
regsub -all {\-name func\M} $txt {-name func_ssinit} txt
regsub -all {\-constraint_mode func\M} $txt {-constraint_mode func_ssinit} txt
regsub -all {(?n)^set_analysis_view.*$} $txt {} txt
uplevel #0 $txt
tv view_tt
tv view_A
puts STA_DIAG_DONE
exit 0
