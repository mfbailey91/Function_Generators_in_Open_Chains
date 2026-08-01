# Sprint V2.8 evidence summary — Shared-Q paired study

**Run id:** `v2_8_shared_q_paired_2r_qu`  
**Package:** `results/v2_8_shared_q_paired_2r_qu/`  
**Config:** `configs/v2/shared_q_paired_2r.yaml`  
**Cardinality:** 5 pairs × 1 task (`cross_range`) × 5 alphas × 3 mechanisms = **75** Dijkstra trials; **50** paired comparisons (four-bar vs span-matched and four-bar vs unit); **0** failures.  
**Figures:** 252 PNGs under `figures/` (lattices including unit-gearbox U, per-pair three-arm \(q(u)\) transmission maps, Q/U/Cartesian path overlays, three-arm expansion charts).

Prior packages `results/v2_8_shared_q_paired_2r/`, `results/v2_8_shared_q_paired_2r_graphs/`, and `results/v2_8_shared_q_paired_2r_unit/` are superseded for dashboard viewing by this run. Active study configs keep only `cross_range` and include the unit-gearbox identity control by default (`study.include_unit_gearbox: true`).

## Null control

At \(\alpha=1\) (pure output distance) every four-bar vs partner case matched on cost, path, and expansions (**10/10**: 5 vs span-matched + 5 vs unit). Unequal feasible nodes were intersected into a shared validity mask across all three arms before search.

## Identity control (unit gearbox)

The unit arm realizes \(q = u\) on the shared output chart. Edge integrals satisfy \(d_U = d_Q\) on every accepted path, and expansion counts are identical across all five alphas for every pair. Selected Q-paths may still differ among equal-cost optima under heap tie-breaking; that is recorded as “equal-cost ties” on the dashboard rather than a failed sanity check.

## Transmission maps

Each pair has one `figures/{pair_id}/qu_axis_maps.png` overlaying \(q_i(u_i)\) for four-bar, span-matched gearbox, and unit gearbox. Each arm is drawn over its own certified \(u\) extent (raw \(u\); the map is fixed per pair and independent of alpha/task). The four-bar and span-matched gearbox share a U box, so nonlinear vs linear transmission reads directly; the unit arm is the \(q=u\) reference on the Q box.

## Objective-weight effects (four-bar vs span-matched)

| \(\alpha\) | Identical Q-paths | Mean \|cost Δ\| |
| --- | ---: | ---: |
| 1.0 | 5/5 | 0 |
| 0.75 | 1/5 | 0.042 |
| 0.5 | 0/5 | 0.083 |
| 0.25 | 0/5 | 0.125 |
| 0.0 | 0/5 | 0.166 |

Path divergence appears as soon as actuator weight is introduced for most pairs. Cost deltas grow monotonically as \(\alpha\) decreases toward pure actuator travel.

## Mechanism nonlinearity

Divergence onset (largest \(\alpha\) with non-identical paths vs span-matched gearbox) is **0.75** for `pair_01`–`pair_03` and `pair_05`, and **0.5** for `pair_04` (still identical at 0.75).

## Task dependence

The active dashboard study uses only **Cross-range**. At the primary mixed weight \(\alpha=0.5\), identical paths vs span-matched are **0/5**.

## Search effort vs path quality

Paired comparison rows record expansion deltas, \(L_U/L_Q/L_X\), node/edge Jaccard overlap, Cartesian separation, and actuator-travel ratios. Expansion changes and path changes do not move in lockstep. Fewer expansions alone is not treated as a quality claim (sprint non-goal). Expansion charts include all three arms (four-bar, span-matched gearbox, unit gearbox).

## Dashboard

Open `results/v2_8_shared_q_paired_2r_qu/index.html` locally. Primary sections are graphical:

- Expansions (by mechanism and by \(\alpha\); three arms)
- Shared Q / U lattices per pair (four-bar, span-matched, unit)
- Transmission maps \(q(u)\) per pair
- Q, U, and Cartesian path overlays
- Null-control gate, identity-control table, paired deltas, trials, and provenance

## Notes

- Grid resolution for this diagnostic package is **12×12** with 5-sample edge traces (sprint sketch suggested 64×64; denser grids remain available by editing the config once performance budgeting allows).
- V2.7 3R work remains held pending review of this dashboard.
