# Accepted r4 ASIC layout renders and RTL-function area aggregates (26 Oct 2026)

These are the **accepted flow-v2 rev4 layouts** of the three Antiphase engines: each final routed checkpoint has
**DRC 0, connectivity 0 (four supplies and full) and timing met** (0 violating setup or hold paths) at the stated
typical-corner clock. The physical and timing figures below come from the runs' own final checks (`final_checks_public.txt`,
`area_public.txt`, final setup/hold summaries; see `work/asic_flow_v2_20261024/ANTIPHASE_R4_RESULTS.md`), not from this render.

| Case | Engine | TT clock | Setup WNS | Hold WNS | DRC | Connectivity | Die (µm) | Placed cells, µm² (std + macro) |
|---|---|---|---|---|---|---|---|---|
| ape_d32_p1150_r4 | D=32 | 1.15 ns | +2 ps | +27 ps | 0 | 0 | 263.3 × 723.1 | 80,822 (60,470 + 20,352) |
| ape_d64_r4 | D=64 | 1.00 ns | +4 ps | +21 ps | 0 | 0 | 277.2 × 1,319.0 | 164,192 (125,834 + 38,358) |
| ape_d128_p1200_r4 | D=128 | 1.20 ns | 0 ps (0 violating paths) | +4 ps | 0 | 0 | 289.8 × 2,510.8 | 334,374 (247,755 + 86,619) |

Produced read-only from each run's `db/final.enc.dat` (flow_v2_20261024, top cells of the D32/D64/D128 engines). Every run
directory was bind-mounted read-only inside the render sandbox; no database was modified or saved, and no file in the run
directories is newer than the render start.
Native work directory: <SCRATCH>/antiphase_asic_20261017/layout_render_r4_20261026T154654Z (on the layout server that
holds the runs).
Scripts (project-authored): `arpeggio/asic/layout/` (render_r4.tcl, batch_r4.sh, png_public.py,
raster.py, rules_ape.json, guard.py, mine.sh, census_r4.py).
Guards: at most 8 CPUs (two 4-CPU slots, taskset 40-47), nice 5, 64 GiB tree-RSS cap, 10,800 s per case; 60-84 s and
5.5-17.5 GiB peak RSS per case. After the batch, a scan of the user's processes (by render tag and working directory)
found none of the render's processes left.
Pass 1 of the same day left the GUI's instance and pin text labels visible; it stays on the server
(`pass1_text_labels/`) and was never exported. The exported renders are pass 2, with GUI text, pin text and violation
layers hidden; the exported PNGs contain no near-white (text) pixels.

Exported files only:
- `<case>_routed_public.png`: Innovus `gui_dump_picture` of the die, square and die-framed (6000 px; all routing layers;
  GUI text and violation overlays hidden), re-encoded as RGB PNG without metadata.
- `<case>_raster_public.npz`: per-pixel dominant RTL-function index and cell occupancy (uint8), pixel = die/1600.
- `<case>_groups_public.json`: per-function instance counts and summed placed cell area; physical-only instances
  (fillers, taps, decaps) excluded and counted.
- `<case>_die_public.txt`: die and core boxes in micrometres and the instance count.
- `<case>_guard_public.json`: render exit status, elapsed time and peak RSS.

Instance names, cell masters, per-instance coordinates, logs and technology files stay on the ASIC servers.
Function groups are assigned by the same ordered regular expressions on RTL instance names as on 24 Oct (rules_ape.json);
synthesized glue without an RTL prefix, and clock and hold buffers, are reported as unattributed (26.7, 31.9 and 30.8% of
placed cell area for D32, D64 and D128). Memory macros take 25.2, 23.4 and 25.9%.
Figure: `figures/asic_layout_r4.pdf` (`tools/figures/make_layout.py`), all three engines at
one scale (1.370 in per mm at column width), dies rotated 90 degrees. The 24 Oct renders and `figures/asic_layout.pdf`
are kept unchanged.
