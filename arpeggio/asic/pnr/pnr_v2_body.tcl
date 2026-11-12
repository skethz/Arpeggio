# Flow v2 body (project-authored), appended on the server to the unchanged kit/init prefix of flow/pnr/pnr.tcl
# (LEF list, init_design, setDesignMode, globalNetConnect). Identical for every engine of the comparison.
# Amendment to PROTOCOL_ASIC section 2 (P&R), applied to all engines: full four-supply mesh with dense over-macro
# supply stripes and explicit stripe-to-port vias (no blockPin extensions), well taps, standard stage order
# (place, CTS, post-CTS hold, route without post-route wire spreading, post-route setup+hold), fillers last.
# Environment: PNR_OUT PNR_UTIL PNR_CPUS FLOW_STOP (pg|place|cts|route|final) FLOW_MAPS (dir with tap/filler/layer maps)
set OUT $::env(PNR_OUT)
set U $::env(PNR_UTIL)
set STOP [expr {[info exists ::env(FLOW_STOP)] ? $::env(FLOW_STOP) : "final"}]
source $::env(FLOW_MAPS)/tap_map_private.tcl
source $::env(FLOW_MAPS)/filler_map_private.tcl
source $::env(FLOW_MAPS)/layer_map_private.tcl
proc v2_step {name script} {
    set f [open $::OUT/${name}_started.txt w]; puts $f [clock seconds]; close $f
    set rc [catch {uplevel 1 $script} message]
    set f [open $::OUT/${name}_status.txt w]; puts $f $rc; close $f
    if {$rc} {
        set f [open $::OUT/${name}_error_private.txt w]; puts $f $message; close $f
        puts "FLOW_V2_STAGE_FAILED $name"; exit 1
    }
    puts "FLOW_V2_STAGE_DONE $name"
}
proc v2_connect_pg {} {
    foreach {net pin} {VDD VDD VSS VSS VDD VCS VNW VNW_N VPW VPW_P VNW VBN VPW VBP} {
        globalNetConnect $net -type pgpin -pin $pin -all -override
    }
    globalNetConnect VDD -type tiehi -all
    globalNetConnect VSS -type tielo -all
}
proc v2_public {name text} {set f [open $::OUT/${name}_public.txt w]; puts $f $text; close $f}
proc v2_count {report} {
    # Total from a verify_drc / verifyConnectivity summary; -1 when absent.
    set f [open $report r]; set t [read $f]; close $f
    if {[regexp -line {^[ \t]*Verification[ \t]+Complete[ \t]*:[ \t]*0[ \t]+Viols} $t]} {return 0}
    if {[regexp -line {No DRC violations were found} $t]} {return 0}
    if {[regexp -line {Found no problems or warnings} $t]} {return 0}
    if {[regexp -line {^[ \t]*Totals?[ \t]+([0-9 \t]+)[ \t]*$} $t all v]} {return [lindex $v end]}
    if {[regexp -line {Verification Complete : ([0-9]+) Viols} $t all v]} {return $v}
    if {[regexp {([0-9]+)[ \t]+(?:total[ \t]+)?[Vv]iolations?} $t all v]} {return $v}
    return -1
}
proc v2_checks {tag} {
    set i 0; set res {}
    foreach net {VDD VSS VNW VPW} {
        verifyConnectivity -type all -net $net -error 1000000 -warning 1000000 -report $::OUT/${tag}_conn_${i}_private.rpt > $::OUT/${tag}_conn_${i}_summary.rpt
        lappend res conn_$i [v2_count $::OUT/${tag}_conn_${i}_summary.rpt]
        incr i
    }
    verifyConnectivity -type all -error 1000000 -warning 1000000 -report $::OUT/${tag}_conn_full_private.rpt > $::OUT/${tag}_conn_full_summary.rpt
    lappend res conn_full [v2_count $::OUT/${tag}_conn_full_summary.rpt]
    clearDrc
    verify_drc -limit 1000000 -report $::OUT/${tag}_drc_private.rpt > $::OUT/${tag}_drc_summary.rpt
    lappend res drc [v2_count $::OUT/${tag}_drc_summary.rpt]
    return $res
}
proc v2_probe {tag} {
    if {![info exists ::env(FLOW_PGPROBE)]} return
    clearDrc
    verify_drc -limit 1000000 -report $::OUT/probe_${tag}_drc_private.rpt > $::OUT/probe_${tag}_drc_summary.rpt
    set f [open $::OUT/probe_${tag}_drc_private.rpt r]; set t [read $f]; close $f
    set c [dict create]
    foreach line [split $t "\n"] {
        if {[regexp {^([A-Z]+): \( ([^)]+) \)[^(]*\( *([A-Za-z0-9]+) *\)} $line all k sub lay]} {dict incr c "$k/$lay"}
    }
    set f [open $::OUT/probe_public.txt a]; puts $f "$tag [lsort -stride 2 -index 0 [dict get $c]]"; close $f
}
setMultiCpuUsage -localCpu $::env(PNR_CPUS)
v2_connect_pg

# ---------------------------------------------------------------- floorplan: macro column on the left core edge
set stdA 0.0
foreach a [dbGet [dbGet top.insts.cell.baseClass core -p2].area] { set stdA [expr {$stdA + $a}] }
set macs [lsort -dictionary [dbGet -e [dbGet top.insts.cell.baseClass block -p2].name]]
set gap 4.0; set chan 8.0; set margin 16.0
set colW 0.0; set colH 0.0; set macA 0.0
foreach m $macs {
    set inst [dbGet top.insts.name $m -p]
    set w [dbGet $inst.cell.size_x]; set h [dbGet $inst.cell.size_y]
    set colW [expr {max($colW, $w)}]; set colH [expr {$colH + $h + $gap}]; set macA [expr {$macA + $w * $h}]
}
set logicA [expr {$stdA / $U}]
if {[llength $macs]} {
    set coreH [expr {max($colH, sqrt($logicA))}]
    set coreW [expr {$colW + $chan + $logicA / $coreH}]
} else {
    set coreH [expr {sqrt($logicA)}]; set coreW $coreH
}
v2_step floorplan {floorPlan -site $site_name -s $coreW $coreH $margin $margin $margin $margin}
set cx [dbGet top.fPlan.coreBox_llx]; set cy [dbGet top.fPlan.coreBox_lly]
set y $cy; set macro_boxes {}
foreach m $macs {
    set inst [dbGet top.insts.name $m -p]
    placeInstance $m $cx $y R0 -fixed
    lappend macro_boxes [lindex [dbGet $inst.box] 0]
    set y [expr {$y + [dbGet $inst.cell.size_y] + $gap}]
}
if {[llength $macs]} {
    addHaloToBlock 1.5 1.5 1.5 1.5 -allBlock
    # Keep standard cells out of the inter-macro gaps and the channel next to the column.
    createPlaceBlockage -box [list $cx $cy [expr {$cx + $colW + $chan / 2}] [expr {$cy + $coreH}]] -type hard -name V2_MACRO_COL
    # No standard-cell rows (hence no follow-pin rails ending against the macros) under the column and half channel.
    cutRow -area [list $cx $cy [expr {$cx + $colW + $chan / 2}] [expr {$cy + $coreH}]]
}
v2_public floorplan [list core_w $coreW core_h $coreH macros [llength $macs] std_area $stdA macro_area $macA util $U]

# ---------------------------------------------------------------- supply network
v2_step taps {addWellTap -cell $tap_cell -cellInterval 20.0 -prefix V2_TAP; v2_connect_pg}
setAddStripeMode -stacked_via_bottom_layer $ap_pg_bottom -stacked_via_top_layer $ap_pg_top
v2_probe taps
v2_step rings {addRing -nets {VDD VSS VNW VPW} -type core_rings -follow core -layer $ap_ring_layers -width 2.0 -spacing 1.0 -offset 1.0}
v2_probe rings
v2_step stripes {addStripe -nets {VDD VSS VNW VPW} -layer $ap_stripe_layer -direction vertical -width 1.0 -spacing 1.0 -set_to_set_distance 40.0 -start_offset 10.0}
v2_probe stripes
if {[llength $macs]} {
    # Dense VDD/VSS stripes over the macro column so that every macro supply strap segment is crossed by a
    # same-net stripe; vias are then dropped from these stripes to the ports (no blockPin extension).
    # Limited horizontally to the macro column; vertically the stripes end on their own core rings.
    v2_step overmacro_stripes {addStripe -nets {VDD VSS} -layer $ap_stripe_layer -direction vertical -width 0.6 -spacing 0.6 -set_to_set_distance 3.0 -start [expr {$cx + 0.4}] -stop [expr {$cx + $colW}]}
    # addStripe already drops stacked vias from these stripes to same-net macro straps (bottom layer M1);
    # explicit editPowerVia vias are added only when FLOW_EDITVIA is set (duplicate stacks otherwise).
    if {[info exists ::env(FLOW_EDITVIA)]} {
        foreach b $macro_boxes {
            v2_step overmacro_vias_[lsearch $macro_boxes $b] {editPowerVia -add_vias true -nets {VDD VSS} -area $b -bottom_layer $macro_pin_layer -top_layer $ap_stripe_layer -orthogonal_only true}
        }
    }
}
v2_probe overmacro
if {[llength $macs]} {
    set nv 0
    foreach mb $macro_boxes {foreach v [dbQuery -areas $mb -objType sViaInst] {if {[dbGet $v.via.botLayer.name] eq $macro_pin_layer} {incr nv}}}
    set f [open $OUT/probe_public.txt a]; puts $f "vias_to_macro_pin_layer $nv"; close $f
}
set ::v2_corepin_target [expr {[info exists ::env(FLOW_COREPIN_TARGET)] ? $::env(FLOW_COREPIN_TARGET) : {none}}]
set pg_range [list $ap_pg_bottom $ap_pg_top]
v2_step followpins {sroute -connect {corePin floatingStripe} -nets {VDD VSS VNW VPW} -layerChangeRange $pg_range -crossoverViaLayerRange $pg_range -targetViaLayerRange $pg_range -corePinTarget $::v2_corepin_target -allowJogging 1 -allowLayerChange 1}
v2_probe followpins
saveDesign $OUT/db/pg.enc
set pg [v2_checks pg]
v2_public pg_checks $pg
if {$STOP eq "pg"} {puts FLOW_V2_DONE_PG; exit 0}

# ---------------------------------------------------------------- placement, clock tree, hold
setPlaceMode -place_global_place_io_pins true
catch {setPlaceMode -place_global_ignore_scan true}
# Constant inputs get tie cells (kit tie-high/tie-low cells, smallest names first) instead of direct rail routes.
set tieh [lindex [lsort [dbGet -e head.libCells.name *TIEHI*]] 0]
set tiel [lindex [lsort [dbGet -e head.libCells.name *TIELO*]] 0]
if {$tieh eq "" || $tiel eq ""} {error "No tie cells found in the loaded libraries"}
setTieHiLoMode -cell [list $tieh $tiel] -maxFanout 16
v2_step place {place_opt_design -out_dir $OUT/reports/place_opt}
v2_step ties {addTieHiLo -prefix V2_TIE}
v2_public ties [list tie_instances [llength [dbGet -e top.insts.name V2_TIE*]]]
saveDesign $OUT/db/place.enc
if {$STOP eq "place"} {puts FLOW_V2_DONE_PLACE; exit 0}
setAnalysisMode -analysisType onChipVariation -cppr both
v2_step cts {clock_opt_design -outDir $OUT/reports/clock_opt}
v2_step postcts_hold {optDesign -postCTS -hold -outDir $OUT/reports/postcts_hold}
saveDesign $OUT/db/cts.enc
# Every filler cell of this kit carries M1 (and implant) obstructions, so fillers go in before routing; the router
# then sees them. Hold is already repaired above, so post-route optimization needs little new placement space.
v2_step fillers {setFillerMode -core $filler_cells -corePrefix V2_FILL -fitGap true -diffCellViol true -add_fillers_with_drc false; addFiller -cell $filler_cells -prefix V2_FILL -doDRC true; v2_connect_pg}
checkFiller > $OUT/filler_check_summary.rpt
timeDesign -postCTS -outDir $OUT/reports/timing_cts > $OUT/timing_cts_summary.rpt
timeDesign -postCTS -hold -outDir $OUT/reports/timing_cts_hold > $OUT/timing_cts_hold_summary.rpt
if {$STOP eq "cts"} {puts FLOW_V2_DONE_CTS; exit 0}

# ---------------------------------------------------------------- routing
set levels {}
foreach name [list $ap_stripe_layer [lindex $ap_ring_layers 1]] {lappend levels [lindex [dbGet [dbGet -p head.layers.name $name].num] 0]}
set levels [lsort -integer -unique $levels]
setNanoRouteMode -routeStripeLayerRange "[lindex $levels 0]:[lindex $levels end]"
foreach pin $tap_secondary_pins {setPGPinUseSignalRoute -well "${tap_cell}:${pin}"}
v2_step well_route {routePGPinUseSignalRoute -well -nets {VNW VPW}}
setNanoRouteMode -routeWithTimingDriven true -routeWithSiDriven true -route_detail_post_route_spread_wire false
v2_step route {routeDesign}
saveDesign $OUT/db/route.enc
setExtractRCMode -engine postRoute
v2_step postroute_opt {optDesign -postRoute -setup -hold -outDir $OUT/reports/postroute_opt}
saveDesign $OUT/db/route_opt.enc
if {$STOP eq "route"} {puts FLOW_V2_DONE_ROUTE; exit 0}

# ---------------------------------------------------------------- fillers last, DRC repair, final checks
# Refill any gaps opened by post-route optimization, then route the ECO.
v2_step refill {addFiller -cell $filler_cells -prefix V2_REFILL -doDRC true; v2_connect_pg}
v2_step eco_route {ecoRoute}
clearDrc
verify_drc -limit 1000000 -report $OUT/pre_eco_drc_private.rpt > $OUT/pre_eco_drc_summary.rpt
if {[v2_count $OUT/pre_eco_drc_summary.rpt] != 0} {setNanoRouteMode -drouteEndIteration 40; v2_step drc_eco {ecoRoute -fix_drc}}
# Final incremental timing optimization after all routing edits (its own ECO route keeps DRC in check).
setOptMode -setupTargetSlack 0.010
v2_step final_opt {optDesign -postRoute -setup -hold -incr -outDir $OUT/reports/final_opt}
setOptMode -setupTargetSlack 0
checkPlace > $OUT/final_place_summary.rpt
v2_step final_extract {extractRC}
timeDesign -postRoute -outDir $OUT/reports/timing_final > $OUT/final_setup_summary.rpt
timeDesign -postRoute -hold -outDir $OUT/reports/timing_final_hold > $OUT/final_hold_summary.rpt
report_timing -max_paths 50 -nworst 1 -path_group reg2reg > $OUT/final_reg2reg_private.rpt
set fin [v2_checks final]
v2_public final_checks $fin
saveDesign $OUT/db/final.enc
saveNetlist $OUT/final_netlist_private.v
catch {write_sdf -min_view view_tt -max_view view_tt -typ_view view_tt $OUT/final_private.sdf}
set die [lindex [dbGet top.fPlan.box] 0]; set core [lindex [dbGet top.fPlan.coreBox] 0]
set stdA2 0.0; set physA 0.0
foreach inst [dbGet top.insts] {
    set a [dbGet $inst.area]
    if {[dbGet $inst.cell.baseClass] eq "core"} {if {[dbGet $inst.isPhysOnly]} {set physA [expr {$physA + $a}]} else {set stdA2 [expr {$stdA2 + $a}]}}
}
v2_public area [list die_um2 [expr {([lindex $die 2]-[lindex $die 0])*([lindex $die 3]-[lindex $die 1])}] core_um2 [expr {([lindex $core 2]-[lindex $core 0])*([lindex $core 3]-[lindex $core 1])}] std_logic_um2 $stdA2 physical_only_um2 $physA macro_um2 $macA]
# Optional: report setup at additional views (e.g. the slow corner) on the final layout, as the clock they support.
if {[info exists ::env(FLOW_REPORT_SETUP_VIEWS)]} {
    foreach v $::env(FLOW_REPORT_SETUP_VIEWS) {
        set_analysis_view -setup [list $v] -hold [list view_tt]
        timeDesign -postRoute -outDir $OUT/reports/timing_final_$v > $OUT/final_setup_${v}_summary.rpt
    }
}
puts FLOW_V2_DONE_FINAL
exit 0
