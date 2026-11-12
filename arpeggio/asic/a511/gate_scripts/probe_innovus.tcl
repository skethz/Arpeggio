# Help probe only (no design, no kit): which analysis commands/options exist in this Innovus build.
foreach c {update_io_latency read_activity_file get_activity report_power set_power_analysis_mode set_interactive_constraint_modes create_analysis_view} {
  puts "PROBE_BEGIN $c exists=[llength [info commands $c]]"
  catch {help $c}
  puts "PROBE_END $c"
}
puts PROBE_DONE
exit 0
