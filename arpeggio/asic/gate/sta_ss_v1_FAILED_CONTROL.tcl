# Slow-corner clock of a saved routed engine (gate_r4, PROTOCOL.md §5). Analysis only: restore, time, nothing optimised
# or saved. SS view = the server MMMC (flow/pnr/mmmc.tcl) evaluated with PNR_CORNER=SSG and renamed objects (no kit path
# here). Constraints = the engine's routed SDC rescaled by sdc_scale.py, plus set_propagated_clock as in the saved mode.
# I/O source latency re-derived per view by update_io_latency -source (the TT closure contract).
# Environment: CL_DB CL_TOP PNR_OUT STA_SDC_BASE STA_ACCEPT_PS STA_START_PS STA_FLOW STA_MACROS STA_CPUS STA_MMMC
setMultiCpuUsage -localCpu $::env(STA_CPUS)
set OUT $::env(PNR_OUT)
file mkdir $OUT/reports
proc pub {name text} {set f [open $::OUT/${name}_public.txt a]; puts $f $text; close $f}
proc wns_groups {report} {
  set f [open $report r]; set t [read $f]; close $f
  set hdr {}; set res {}
  foreach line [split $t "\n"] {
    if {[regexp {^\|\s+(Setup|Hold) mode\s+\|(.*)\|\s*$} $line all m rest]} {set hdr [lmap x [split $rest |] {string trim $x}]}
    if {$hdr ne {} && [regexp {^\|\s+WNS \(ns\):\|(.*)\|\s*$} $line all rest]} {
      set vals [lmap x [split $rest |] {string trim $x}]
      foreach h $hdr v $vals {if {$h ne ""} {lappend res $h $v}}
      return $res
    }
  }
  return {all NA}
}
proc ok_all {g} {foreach {k v} $g {if {![string is double -strict $v] || $v < 0} {return 0}}; return 1}
proc ok_int {g} {foreach {k v} $g {if {$k in {reg2reg reg2cgate} && (![string is double -strict $v] || $v < 0)} {return 0}}; return 1}
proc latency_of {view tag} {
  catch {write_sdc -view $view $::OUT/${tag}_private.sdc}
  set lat NA
  if {[file exists $::OUT/${tag}_private.sdc]} {
    set f [open $::OUT/${tag}_private.sdc r]; set t [read $f]; close $f
    set v {}
    foreach line [split $t "\n"] {if {[regexp {set_clock_latency\s+-source.*?(-?[0-9]+\.?[0-9]*)\s+\[get_ports} $line all x]} {lappend v $x}}
    if {[llength $v]} {set lat [lsort -real -unique $v]}
  }
  return $lat
}
proc scaled_sdc {p} {
  exec python3 $::env(STA_FLOW)/sdc_scale.py $::env(STA_SDC_BASE) $::OUT/sdc_p$p.sdc $p
  set f [open $::OUT/sdc_p$p.sdc a]; puts $f "set_propagated_clock \[get_ports {clk}\]"; close $f
  return $::OUT/sdc_p$p.sdc
}
proc eval_view {name dc p} {
  create_constraint_mode -name func_$name -sdc_files [list [scaled_sdc $p]]
  create_analysis_view -name view_$name -constraint_mode func_$name -delay_corner $dc
  set_analysis_view -setup [list view_$name] -hold [list view_$name]
  set rc [catch {update_io_latency -source -verbose} e]
  set method update_io_latency
  if {$rc} {
    # fallback (logged): source latency = -(mean clock arrival at register clock pins) with zero source latency
    set s 0.0; set n 0
    foreach_in_collection pin [all_registers -clock_pins] {
      set a [get_property $pin arrival_max_rise]
      if {[string is double -strict $a]} {set s [expr {$s + $a}]; incr n}
    }
    set method mean_sink_arrival_n$n
    if {$n} {
      set_interactive_constraint_modes [list func_$name]
      set_clock_latency -source [expr {-$s / $n}] [get_ports {clk}] -clock clk
      set_interactive_constraint_modes {}
    }
  }
  pub io_latency "$name update_io_latency_rc $rc method $method source_latency_ps [latency_of view_$name lat_$name]"
  timeDesign -postRoute -outDir $::OUT/reports/$name > $::OUT/${name}_setup_summary.rpt
  set g [wns_groups $::OUT/${name}_setup_summary.rpt]
  pub setup "$name period_ps $p $g"
  return $g
}
restoreDesign $::env(CL_DB) $::env(CL_TOP)
setExtractRCMode -engine postRoute
setAnalysisMode -analysisType onChipVariation -cppr both
# control 1: the accepted TT view exactly as saved
set_analysis_view -setup [list view_tt] -hold [list view_tt]
timeDesign -postRoute -outDir $OUT/reports/tt_saved > $OUT/tt_saved_setup_summary.rpt
timeDesign -postRoute -hold -outDir $OUT/reports/tt_saved_hold > $OUT/tt_saved_hold_summary.rpt
pub control "tt_saved setup [wns_groups $OUT/tt_saved_setup_summary.rpt] hold [wns_groups $OUT/tt_saved_hold_summary.rpt] latency_saved_ps [latency_of view_tt lat_tt_saved]"
# SS corner objects from the server MMMC (renamed); its own mode/view are created once and not used for results
set ::env(PNR_CORNER) SSG
set f [open $::env(STA_MACROS) r]; set ::env(PNR_MACROS) [string trim [read $f]]; close $f
set ::env(PNR_SDC) [scaled_sdc $::env(STA_START_PS)]
set f [open $::env(STA_MMMC) r]; set txt [read $f]; close $f
foreach {a b} {lib_tt lib_ss rc_nom rc_ss dc_tt dc_ss view_tt view_ssinit} {regsub -all "\\m$a\\M" $txt $b txt}
regsub -all {\-name func\M} $txt {-name func_ssinit} txt
regsub -all {\-constraint_mode func\M} $txt {-constraint_mode func_ssinit} txt
regsub -all {(?n)^set_analysis_view.*$} $txt {} txt
uplevel #0 $txt
# control 2: the same procedure at TT, accepted period
set g [eval_view tt_ctl dc_tt $::env(STA_ACCEPT_PS)]
pub control "tt_procedure period_ps $::env(STA_ACCEPT_PS) $g"
# walk at SS (50 ps steps): bracket the all-groups boundary, then the internal-only (reg2reg+reg2cgate) boundary
set p $::env(STA_START_PS); set res [dict create]; set n 0
set g [eval_view ss_p$p dc_ss $p]; dict set res $p $g; incr n
if {[ok_all $g]} {
  while {$n < 14} {set q [expr {$p - 50}]; set g [eval_view ss_p$q dc_ss $q]; dict set res $q $g; incr n; if {![ok_all $g]} break; set p $q}
} else {
  while {$n < 14} {set p [expr {$p + 50}]; set g [eval_view ss_p$p dc_ss $p]; dict set res $p $g; incr n; if {[ok_all $g]} break}
}
set p_all NA; foreach q [lsort -integer [dict keys $res]] {if {[ok_all [dict get $res $q]]} {set p_all $q; break}}
set q [lindex [lsort -integer [dict keys $res]] 0]
while {$n < 26 && [ok_int [dict get $res $q]]} {set q [expr {$q - 50}]; set g [eval_view ss_p$q dc_ss $q]; dict set res $q $g; incr n}
set p_int NA; foreach q [lsort -integer [dict keys $res]] {if {[ok_int [dict get $res $q]]} {set p_int $q; break}}
pub result "ss_clock_all_groups_ps $p_all ss_clock_internal_ps $p_int evaluations $n"
# SS hold at the SS clock
if {$p_all ne "NA"} {
  set_analysis_view -setup [list view_ss_p$p_all] -hold [list view_ss_p$p_all]
  timeDesign -postRoute -hold -outDir $OUT/reports/ss_hold_p$p_all > $OUT/ss_hold_p${p_all}_summary.rpt
  pub result "ss_hold_at_ss_clock period_ps $p_all [wns_groups $OUT/ss_hold_p${p_all}_summary.rpt]"
}
puts STA_DONE
exit 0
