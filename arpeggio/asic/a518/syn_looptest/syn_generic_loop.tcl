# Shared Genus 25.11 synthesis for every engine of the Antiphase ASIC comparison (same library, corner, constraints).
# Kit paths come from <KIT_SYN_SETUP> (not included). Environment:
#   SYN_TOP top module; SYN_FILES HDL files (space separated); SYN_DEFINES `define list (space separated, optional);
#   SYN_PARAMS elaborate parameters "NAME=VAL ..." (optional); SYN_OUT run directory; SYN_PERIOD clock period (ps);
#   SYN_CPUS threads; SYN_MACROS macro names (views under macros_gen, optional); SYN_RETIME module-name glob (optional);
#   SYN_CLK clock port name (default clk); SYN_STOP "elab" to stop after elaboration; SYN_EFFORT (default medium).
set R      <SCRATCH>/antiphase_asic_20261017
set TOP    $::env(SYN_TOP)
set OUT    $::env(SYN_OUT)
set PER    $::env(SYN_PERIOD)
set CPUS   $::env(SYN_CPUS)
proc envd {n d} { if {[info exists ::env($n)] && $::env($n) ne ""} { return $::env($n) } ; return $d }
set CLK    [envd SYN_CLK clk]
set STOP   [envd SYN_STOP ""]
set EFF    [envd SYN_EFFORT medium]
set MACROS [envd SYN_MACROS ""]
file mkdir $OUT/reports $OUT/out
set_db max_cpus_per_server $CPUS
set_db information_level 7
set_db hdl_error_on_blackbox true
set_db hdl_max_loop_limit [envd SYN_LOOP_LIMIT 4096]
set_db lp_insert_clock_gating true

# Kit libraries, LEFs and the QRC file are set by a server-only kit file that is not included. It defines $libs
# (standard-cell and memory-macro timing libraries at TT 0.80 V, 25 C or, with SYN_CORNER SSG, 0.72 V, 125 C),
# $lefs (technology, standard-cell and macro LEFs) and $QRC_FILE (nominal RC at TT, FuncRCmax at SSG).
set CRN [envd SYN_CORNER TT]
source <KIT_SYN_SETUP>
puts "SYN_INFO corner $CRN"
read_libs $libs
read_physical -lef $lefs
set_db qrc_tech_file $QRC_FILE
set_db interconnect_mode ple

set defs [envd SYN_DEFINES ""]
set dflags {}
foreach d $defs { lappend dflags -define $d }
read_hdl -language sv {*}$dflags $::env(SYN_FILES)
set params [envd SYN_PARAMS ""]
if {$params ne ""} {
    set plist {}
    foreach kv $params { set p [split $kv =]; lappend plist [list [lindex $p 0] [lindex $p 1]] }
    elaborate $TOP -parameters $plist
} else { elaborate $TOP }
set DES [lindex [get_db designs] 0]
current_design $DES
puts "SYN_INFO design [get_db $DES .name]"
check_design -unresolved > $OUT/reports/check_design_unresolved.rpt
check_design > $OUT/reports/check_design.rpt

create_clock -name clk -period $PER [get_ports $CLK]
set_clock_uncertainty -setup [expr {0.05 * $PER}] [get_clocks clk]
set_input_delay  -clock clk [expr {0.25 * $PER}] [all_inputs -no_clocks]
set_output_delay -clock clk [expr {0.25 * $PER}] [all_outputs]
set_input_transition 50 [all_inputs]
set_load 5 [all_outputs]
puts "SYN_INFO top=$TOP period_ps=$PER cpus=$CPUS macros=[llength $MACROS]"
write_sdc > $OUT/out/constraints_in.sdc
set rt [envd SYN_RETIME ""]
if {$rt ne ""} {
    set mods [get_db modules -if ".name == $rt"]
    if {[llength $mods]} { set_db $mods .retime true }
    puts "SYN_INFO retime modules: [get_db $mods .name]"
}
if {$STOP eq "elab"} { report_hierarchy > $OUT/reports/hier.rpt; exit }
set_db syn_generic_effort $EFF
set_db syn_map_effort $EFF
set_db syn_opt_effort $EFF
syn_generic
syn_map
syn_opt
write_db -to_file $OUT/out/opt.db
report_timing -max_paths 20 -nworst 1 > $OUT/reports/timing.rpt
report_qor > $OUT/reports/qor.rpt
report_area > $OUT/reports/area.rpt
report_area -depth 3 > $OUT/reports/area_d3.rpt
report_gates > $OUT/reports/gates_SERVER_ONLY.rpt
report_clock_gating > $OUT/reports/clock_gating.rpt
report_power > $OUT/reports/power_vectorless.rpt
write_hdl > $OUT/out/netlist.v
write_sdc > $OUT/out/final.sdc
puts "SYN_DONE $OUT"
exit
