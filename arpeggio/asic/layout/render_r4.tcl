# Read-only r4 render (26 Oct 2026): restore an accepted final checkpoint (never saved), write die/core boxes and a
# private per-instance table, then dump one square, die-framed routed view with GUI violation overlays and all GUI
# text (instance, pin and net labels) hidden. Pass 1 (26 Oct) lacked the text switches and is kept server-side only.
setMultiCpuUsage -localCpu 4
set OUT $::env(PNR_OUT)
proc mark {x} {set f [open $::OUT/phase.txt w];puts $f $x;close $f}
mark restore
restoreDesign $::env(PP_DB) $::env(PP_TOP)
mark extract
set die [lindex [dbGet top.fPlan.box] 0]
set core [lindex [dbGet top.fPlan.coreBox] 0]
set f [open $OUT/die_public.txt w];puts $f "die $die";puts $f "core $core";puts $f "insts [llength [dbGet top.insts]]";close $f
set f [open $OUT/insts_private.tsv w]
foreach n [dbGet top.insts.name] p [dbGet top.insts.isPhysOnly] c [dbGet top.insts.cell.baseClass] b [dbGet top.insts.box] {
  puts $f "$n\t$p\t$c\t[join [string map {\{ {} \} {}} $b] { }]"
}
close $f
mark render
foreach n {text pinText violation marker markers drcMarker ruler userGrid flightLine} {catch {setLayerPreference $n -isVisible 0}}
zoomBox [lindex $die 0] [lindex $die 1] [lindex $die 2] [lindex $die 3]
gui_dump_picture $OUT/routed_sq_raw.png -format PNG -width $::env(SQ) -height $::env(SQ)
mark complete
puts RENDER_R4_DONE
exit 0
