# Slow-corner clock of a saved routed engine (gate_r4, PROTOCOL.md §5 with amendment A2). Analysis only: restore, time,
# nothing optimised or saved. SS objects from the server MMMC (PNR_CORNER=SSG, renamed). Constraints: the engine's routed
# SDC rescaled by sdc_scale.py + set_propagated_clock (as the saved mode). I/O source-latency rules, each walked at 50 ps:
#   R2 re-derived: a latency file (ccopt's form, 8 lines) = -(mean clock arrival at register clock pins, rise/fall) measured
#      in that corner with zero source latency (the TT closure contract: sinks at the ideal edge);
#   R1 the saved TT latency file unchanged;  R0 no source latency (as an earlier project STA script).
# Primary = R2 if, at TT and the accepted period, R2 reproduces the accepted WNS (all groups) within 5 ps; else R1.
# Environment: CL_DB CL_TOP PNR_OUT STA_SDC_BASE STA_ACCEPT_PS STA_START_PS STA_FLOW STA_MACROS STA_CPUS STA_MMMC
setMultiCpuUsage -localCpu $::env(STA_CPUS)
set OUT $::env(PNR_OUT)
file mkdir $OUT/reports
proc pub {name text} {set f [open $::OUT/${name}_public.txt a]; puts $f $text; close $f}
proc wns_groups {report} {
  set f [open $report r]; set t [read $f]; close $f
  set hdr {}
  foreach line [split $t "\n"] {
    if {[regexp {^\|\s+(Setup|Hold) mode\s+\|(.*)\|\s*$} $line all m rest]} {set hdr [lmap x [split $rest |] {string trim $x}]}
    if {$hdr ne {} && [regexp {^\|\s+WNS \(ns\):\|(.*)\|\s*$} $line all rest]} {
      set res {}; foreach h $hdr v [lmap x [split $rest |] {string trim $x}] {if {$h ne ""} {lappend res $h $v}}; return $res
    }
  }
  return {all NA}
}
proc gget {g k} {foreach {a b} $g {if {$a eq $k} {return $b}}; return NA}
proc ok_all {g} {foreach {k v} $g {if {![string is double -strict $v] || $v < 0} {return 0}}; return 1}
proc ok_int {g} {foreach {k v} $g {if {$k in {reg2reg reg2cgate} && (![string is double -strict $v] || $v < 0)} {return 0}}; return 1}
proc scaled_sdc {p} {
  set s $::OUT/sdc_p$p.sdc
  if {![file exists $s]} {
    exec python3 $::env(STA_FLOW)/sdc_scale.py $::env(STA_SDC_BASE) $s $p
    set f [open $s a]; puts $f "set_propagated_clock \[get_ports {clk}\]"; close $f
  }
  return $s
}
proc mode_for {p} {
  if {![info exists ::MODES(func_p$p)]} {create_constraint_mode -name func_p$p -sdc_files [list [scaled_sdc $p]]; set ::MODES(func_p$p) 1}
  return func_p$p
}
proc time_view {view} {
  set_analysis_view -setup [list $view] -hold [list $view]
  timeDesign -postRoute -outDir $::OUT/reports/$view > $::OUT/${view}_setup_summary.rpt
  return [wns_groups $::OUT/${view}_setup_summary.rpt]
}
proc mean_arrivals {} {
  set sr 0.0; set sf 0.0; set n 0
  foreach_in_collection pin [all_registers -clock_pins] {
    set r [get_property $pin arrival_max_rise]; set f [get_property $pin arrival_max_fall]
    if {[string is double -strict $r] && [string is double -strict $f]} {set sr [expr {$sr + $r}]; set sf [expr {$sf + $f}]; incr n}
  }
  return [list [expr {$sr / $n}] [expr {$sf / $n}] $n]
}
proc write_lat {file r f} {
  set fo [open $file w]
  foreach ef {early late} { foreach mm {min max} {
    puts $fo "set_clock_latency -source -$ef -$mm -rise [format %.3f [expr {-$r}]] \[get_ports {clk}\] -clock clk"
    puts $fo "set_clock_latency -source -$ef -$mm -fall [format %.3f [expr {-$f}]] \[get_ports {clk}\] -clock clk" } }
  close $fo
}
# view for (rule, corner, period); R2 needs the corner's latency file in ::LAT($dc)
proc view_for {rule dc p} {
  set v view_${rule}_${dc}_p$p
  if {![info exists ::VIEWS($v)]} {
    set ::VIEWS($v) 1
    set m [mode_for $p]
    switch $rule {
      R0 {create_analysis_view -name $v -constraint_mode $m -delay_corner $dc}
      R1 {create_analysis_view -name $v -constraint_mode $m -delay_corner $dc -latency_file $::SAVED_LAT}
      R2 {create_analysis_view -name $v -constraint_mode $m -delay_corner $dc -latency_file $::LAT($dc)}
    }
  }
  return $v
}
proc eval_rule {rule dc p} {
  set g [time_view [view_for $rule $dc $p]]
  pub setup "$rule $dc period_ps $p $g"
  return $g
}
restoreDesign $::env(CL_DB) $::env(CL_TOP)
set ::SAVED_LAT $::env(CL_DB)/mmmc/views/view_tt/latency.sdc
setExtractRCMode -engine postRoute
setAnalysisMode -analysisType onChipVariation -cppr both
set g0 [time_view view_tt]
pub control "saved view_tt setup $g0"
# SS corner objects (renamed copy of the server MMMC; its own init mode/view are not used for results)
set ::env(PNR_CORNER) SSG
set f [open $::env(STA_MACROS) r]; set ::env(PNR_MACROS) [string trim [read $f]]; close $f
set ::env(PNR_SDC) [scaled_sdc $::env(STA_START_PS)]
set f [open $::env(STA_MMMC) r]; set txt [read $f]; close $f
foreach {a b} {lib_tt lib_ss rc_nom rc_ss dc_tt dc_ss view_tt view_ssinit} {regsub -all "\\m$a\\M" $txt $b txt}
regsub -all {\-name func\M} $txt {-name func_ssinit} txt
regsub -all {\-constraint_mode func\M} $txt {-constraint_mode func_ssinit} txt
regsub -all {(?n)^set_analysis_view.*$} $txt {} txt
uplevel #0 $txt
# mean sink arrival with zero source latency, per corner (independent of the period)
foreach {dc p} [list dc_tt $::env(STA_ACCEPT_PS) dc_ss $::env(STA_START_PS)] {
  set g [eval_rule R0 $dc $p]
  set_analysis_view -setup [list [view_for R0 $dc $p]] -hold [list [view_for R0 $dc $p]]
  set ma [mean_arrivals]
  set ::LAT($dc) $OUT/lat_r2_$dc.sdc
  write_lat $::LAT($dc) [lindex $ma 0] [lindex $ma 1]
  pub latency "$dc mean_sink_arrival_rise_ps [format %.3f [lindex $ma 0]] fall_ps [format %.3f [lindex $ma 1]] sinks [lindex $ma 2]"
}
# TT calibration at the accepted period
set g1 [eval_rule R1 dc_tt $::env(STA_ACCEPT_PS)]
set g2 [eval_rule R2 dc_tt $::env(STA_ACCEPT_PS)]
set d2 [expr {abs([gget $g2 all] - [gget $g0 all]) * 1000.0}]
set primary [expr {$d2 <= 5.0 ? "R2" : "R1"}]
pub control "tt_calibration R1 $g1 R2 $g2 R2_delta_all_ps [format %.1f $d2] primary $primary"
# SS walks, one per rule (primary first), then the internal-only boundary from the same rule's evaluations
set n 0
foreach rule [concat $primary [lsearch -all -inline -not -exact {R2 R1 R0} $primary]] {
  set res [dict create]
  set p $::env(STA_START_PS)
  set g [eval_rule $rule dc_ss $p]; dict set res $p $g; incr n
  if {[ok_all $g]} {
    for {set k 0} {$k < 12} {incr k} {set q [expr {$p - 50}]; set g [eval_rule $rule dc_ss $q]; dict set res $q $g; incr n; if {![ok_all $g]} break; set p $q}
  } else {
    for {set k 0} {$k < 12} {incr k} {set p [expr {$p + 50}]; set g [eval_rule $rule dc_ss $p]; dict set res $p $g; incr n; if {[ok_all $g]} break}
  }
  set q [lindex [lsort -integer [dict keys $res]] 0]
  for {set k 0} {$k < 12 && [ok_int [dict get $res $q]]} {incr k} {set q [expr {$q - 50}]; set g [eval_rule $rule dc_ss $q]; dict set res $q $g; incr n}
  set p_all NA; foreach q [lsort -integer [dict keys $res]] {if {[ok_all [dict get $res $q]]} {set p_all $q; break}}
  set p_int NA; foreach q [lsort -integer [dict keys $res]] {if {[ok_int [dict get $res $q]]} {set p_int $q; break}}
  # monotonicity check over the evaluated periods (all-groups pass set must be an upper interval)
  set mono 1; set seen 0; foreach q [lsort -integer [dict keys $res]] {set o [ok_all [dict get $res $q]]; if {$seen && !$o} {set mono 0}; if {$o} {set seen 1}}
  pub result "$rule ss_clock_all_groups_ps $p_all ss_clock_internal_ps $p_int monotone $mono"
  if {$rule eq $primary && $p_all ne "NA"} {
    set v [view_for $rule dc_ss $p_all]
    set_analysis_view -setup [list $v] -hold [list $v]
    timeDesign -postRoute -hold -outDir $OUT/reports/ss_hold_p$p_all > $OUT/ss_hold_p${p_all}_summary.rpt
    pub result "$rule ss_hold_at_ss_clock period_ps $p_all [wns_groups $OUT/ss_hold_p${p_all}_summary.rpt]"
  }
}
puts STA_DONE
exit 0
