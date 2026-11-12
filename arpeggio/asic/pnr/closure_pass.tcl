# Closure pass (project-authored): on a finished flow-v2 layout, one incremental post-route setup/hold optimization,
# refill, DRC ECO, then the same final checks and reports as the flow. Constraints and floorplan are unchanged.
# Environment: CL_DB (final.enc.dat), CL_TOP, PNR_OUT (new dir), FLOW_MAPS, optional FLOW_REPORT_SETUP_VIEWS.
setMultiCpuUsage -localCpu 8
set OUT $::env(PNR_OUT)
file mkdir $OUT/db $OUT/reports
source $::env(FLOW_MAPS)/filler_map_private.tcl
proc v2_step {name script} {
    set f [open $::OUT/${name}_started.txt w]; puts $f [clock seconds]; close $f
    set rc [catch {uplevel 1 $script} message]
    set f [open $::OUT/${name}_status.txt w]; puts $f $rc; close $f
    if {$rc} {set f [open $::OUT/${name}_error_private.txt w]; puts $f $message; close $f; puts "FLOW_V2_STAGE_FAILED $name"; exit 1}
    puts "FLOW_V2_STAGE_DONE $name"
}
proc v2_connect_pg {} {
    foreach {net pin} {VDD VDD VSS VSS VDD VCS VNW VNW_N VPW VPW_P VNW VBN VPW VBP} {globalNetConnect $net -type pgpin -pin $pin -all -override}
    globalNetConnect VDD -type tiehi -all
    globalNetConnect VSS -type tielo -all
}
proc v2_public {name text} {set f [open $::OUT/${name}_public.txt w]; puts $f $text; close $f}
proc v2_count {report} {
    set f [open $report r]; set t [read $f]; close $f
    if {[regexp -line {^[ \t]*Verification[ \t]+Complete[ \t]*:[ \t]*0[ \t]+Viols} $t]} {return 0}
    if {[regexp -line {No DRC violations were found} $t]} {return 0}
    if {[regexp -line {Found no problems or warnings} $t]} {return 0}
    if {[regexp -line {Verification Complete : ([0-9]+) Viols} $t all v]} {return $v}
    if {[regexp -line {^[ \t]*Totals?[ \t]+([0-9 \t]+)[ \t]*$} $t all v]} {return [lindex $v end]}
    return -1
}
proc v2_checks {tag} {
    set i 0; set res {}
    foreach net {VDD VSS VNW VPW} {
        verifyConnectivity -type all -net $net -error 1000000 -warning 1000000 -report $::OUT/${tag}_conn_${i}_private.rpt > $::OUT/${tag}_conn_${i}_summary.rpt
        lappend res conn_$i [v2_count $::OUT/${tag}_conn_${i}_summary.rpt]; incr i
    }
    verifyConnectivity -type all -error 1000000 -warning 1000000 -report $::OUT/${tag}_conn_full_private.rpt > $::OUT/${tag}_conn_full_summary.rpt
    lappend res conn_full [v2_count $::OUT/${tag}_conn_full_summary.rpt]
    clearDrc
    verify_drc -limit 1000000 -report $::OUT/${tag}_drc_private.rpt > $::OUT/${tag}_drc_summary.rpt
    lappend res drc [v2_count $::OUT/${tag}_drc_summary.rpt]
    return $res
}
restoreDesign $::env(CL_DB) $::env(CL_TOP)
setExtractRCMode -engine postRoute
setAnalysisMode -analysisType onChipVariation -cppr both
setNanoRouteMode -route_detail_post_route_spread_wire false
# Optimize toward a small positive setup margin so later routing touch-ups cannot push WNS below zero;
# the reported timing below uses the unchanged constraints (no margin).
set m [expr {[info exists ::env(CL_SETUP_MARGIN)] ? $::env(CL_SETUP_MARGIN) : 0.010}]
setOptMode -setupTargetSlack $m
v2_public closure_margin [list setup_target_slack_ns $m]
v2_step closure_opt {optDesign -postRoute -setup -hold -incr -outDir $OUT/reports/closure_opt}
setOptMode -setupTargetSlack 0
v2_step refill {addFiller -cell $filler_cells -prefix V2_CLFILL -doDRC true; v2_connect_pg}
v2_step eco_route {ecoRoute}
clearDrc
verify_drc -limit 1000000 -report $OUT/pre_eco_drc_private.rpt > $OUT/pre_eco_drc_summary.rpt
if {[v2_count $OUT/pre_eco_drc_summary.rpt] != 0} {
    setNanoRouteMode -drouteEndIteration 40
    v2_step drc_eco {ecoRoute -fix_drc}
}
checkPlace > $OUT/final_place_summary.rpt
v2_step final_extract {extractRC}
timeDesign -postRoute -outDir $OUT/reports/timing_final > $OUT/final_setup_summary.rpt
timeDesign -postRoute -hold -outDir $OUT/reports/timing_final_hold > $OUT/final_hold_summary.rpt
set fin [v2_checks final]
v2_public final_checks $fin
saveDesign $OUT/db/final.enc
saveNetlist $OUT/final_netlist_private.v
set die [lindex [dbGet top.fPlan.box] 0]; set core [lindex [dbGet top.fPlan.coreBox] 0]
set stdA2 0.0; set physA 0.0; set macA 0.0
foreach inst [dbGet top.insts] {
    set a [dbGet $inst.area]
    if {[dbGet $inst.cell.baseClass] eq "block"} {set macA [expr {$macA + $a}]} elseif {[dbGet $inst.isPhysOnly]} {set physA [expr {$physA + $a}]} else {set stdA2 [expr {$stdA2 + $a}]}
}
v2_public area [list die_um2 [expr {([lindex $die 2]-[lindex $die 0])*([lindex $die 3]-[lindex $die 1])}] core_um2 [expr {([lindex $core 2]-[lindex $core 0])*([lindex $core 3]-[lindex $core 1])}] std_logic_um2 $stdA2 physical_only_um2 $physA macro_um2 $macA]
if {[info exists ::env(FLOW_REPORT_SETUP_VIEWS)]} {
    foreach v $::env(FLOW_REPORT_SETUP_VIEWS) {
        set_analysis_view -setup [list $v] -hold [list view_tt]
        timeDesign -postRoute -outDir $OUT/reports/timing_final_$v > $OUT/final_setup_${v}_summary.rpt
    }
}
puts FLOW_V2_DONE_FINAL
exit 0
