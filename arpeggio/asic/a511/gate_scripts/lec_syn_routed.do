tclmode
# Synthesis netlist (golden) vs final routed netlist (revised); project-authored (PROTOCOL.md §3.2, as an earlier project power flow).
# Libraries (std cells + the TT macro views) come from the server-only libs_private.do, extracted from Genus' own dofile.
# Macros are black boxes on both sides (add_notranslate_modules -library, as Genus' dofile).
set_screen_display -noprogress
set_dofile_abort exit
set_log_file $env(L_WORK)/lec.log -replace
usage -auto -elapse
set_parallel_option -threads 1,$env(L_THREADS) -norelease_license
set_compare_options -threads 1,$env(L_THREADS)
set_undefined_cell black_box -noascend -both
source $env(L_WORK)/libs_private.do
read_design -verilog95 -golden -lastmod -noelab $env(L_GOLDEN)
elaborate_design -golden -root $env(L_TOP)
read_design -verilog95 -revised -lastmod -noelab $env(L_REVISED)
elaborate_design -revised -root $env(L_TOP)
report_design_data
report_black_box
set_flatten_model -seq_constant
set_flatten_model -seq_constant_x_to 0
set_flatten_model -gated_clock
set_mapping_method -name first
set_system_mode lec
report_unmapped_points -summary
report_unmapped_points -notmapped
add_compared_points -all
compare
report_compare_data -class nonequivalent -class abort -class notcompared
report_verification -verbose
report_statistics
puts "LEC_COUNTS compare [get_compare_points -count] equivalent [get_compare_points -equivalent -count] noneq [get_compare_points -NONequivalent -count] abort [get_compare_points -abort -count] unknown [get_compare_points -unknown -count]"
puts "LEC_BBOX golden [llength [get_black_boxes -golden]] revised [llength [get_black_boxes -revised]]"
exit
