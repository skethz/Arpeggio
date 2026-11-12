# Amendment A5.2 (exploratory, not pre-registered): parallel-trial tuning grid extended below its corner

**Approved and dated.** The coordinator approved this on Sun 25 Oct 2026, about 07:35 CET, and it was written and frozen before any A5.2 run. It does **not** replace the frozen A5d verdict (RESULTS.md §A5d: not killed); it is reported beside it.

**Why.** Every equal-cycles pick in the frozen 12-cell grid sits at its lowest T0 (0.3), a grid corner. The chair flags corner optima as a bias.

**What runs.**
- **Extension cells.** T0 ∈ {0.075, 0.15} × T1 ∈ {0.0125, 0.025, 0.05}, for both budgets (equal modelled cycles; equal flips), at P1, P2 and P3 on tuning seed 1000. That is 36 cells, with the same uses per cell as A5: 4,000 at P1/P3 and 2,000 at P2.
- **Selection.** Each budget and point gets a pick over the union of the frozen 12 cells and the 6 new ones. The rule is unchanged (fewest bit errors, then fewest erroneous uses, then order, frozen cells first). Script: `src/select_a52.py`, output `results/a52_sel.json`.
- **Held-out re-runs.** Every pick is re-run on seed 102, on the same draws as (i), with the A5 stopping rule:
  - the P1 pick reused at P2/P3, which is the kill-arm privilege (`abl_pt2c_*`, `abl_pt2f_*`);
  - the per-point picks (`abl_pt2cp_*`, `abl_pt2fp_*`).
- **Reporting.** Paired-bootstrap BER-ratio CIs and McNemar against (i). The frozen kill rule is applied to the A5.2 kill arm for information.
- **Mandatory statement.** If the A5.2 kill arm has an upper CI ≤ 1 at P1, that is stated plainly, and likewise for any other point.

**Compute.** Three extra workers on hostB GPU0 (`src/supervise_a52.sh`), under the same foreign-process check and the 24-core CPU cap. Estimated time: about 30–45 min.
