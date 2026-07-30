# Sprint V2.8 evidence summary — Shared-Q paired study

**Run id:** `v2_8_shared_q_paired_2r_graphs`  
**Package:** `results/v2_8_shared_q_paired_2r_graphs/`  
**Config:** `configs/v2/shared_q_paired_2r.yaml`  
**Cardinality:** 5 pairs × 1 task (`cross_range`) × 5 alphas × 2 mechanisms = **50** Dijkstra trials; **25** paired comparisons; **0** failures.  
**Figures:** 167 PNGs under `figures/` (lattices, Q/U/Cartesian path overlays with start/goal poses, expansion charts).

The prior tables-only package `results/v2_8_shared_q_paired_2r/` (3 task templates, empty `figures/`) is superseded for dashboard viewing by this graphical run. Active study configs keep only `cross_range`.

## Null control

At \(\alpha=1\) (pure output distance) every pair–task case matched on cost, path, and expansions (**5/5**). Unequal feasible nodes were intersected into a shared validity mask before search so topology identity is an invariant, not an average.

## Objective-weight effects

| \(\alpha\) | Identical Q-paths | Mean \|cost Δ\| |
| --- | ---: | ---: |
| 1.0 | 5/5 | 0 |
| 0.75 | 1/5 | 0.042 |
| 0.5 | 0/5 | 0.083 |
| 0.25 | 0/5 | 0.125 |
| 0.0 | 0/5 | 0.166 |

Path divergence appears as soon as actuator weight is introduced for most pairs. Cost deltas grow monotonically as \(\alpha\) decreases toward pure actuator travel.

## Mechanism nonlinearity

Divergence onset (largest \(\alpha\) with non-identical paths) is **0.75** for `pair_01`–`pair_03` and `pair_05`, and **0.5** for `pair_04` (still identical at 0.75). Asymmetric / joint-distinct structure in `pair_04` delays path divergence relative to the other frozen fixtures on this cross-range query.

## Task dependence

The active dashboard study uses only **Cross-range**. At the primary mixed weight \(\alpha=0.5\), identical paths are **0/5**.

## Search effort vs path quality

Paired comparison rows record expansion deltas, \(L_U/L_Q/L_X\), node/edge Jaccard overlap, Cartesian separation, and actuator-travel ratios. Expansion changes and path changes do not move in lockstep: some cases diverge in selected Q-path while expansion counts remain close. Fewer expansions alone is not treated as a quality claim (sprint non-goal).

## Dashboard

Open `results/v2_8_shared_q_paired_2r_graphs/index.html` locally. Primary sections are graphical:

- Expansions (by mechanism and by \(\alpha\))
- Shared Q / U lattices per pair
- Q, U, and Cartesian path overlays (start/goal markers; Cartesian includes stick poses)
- Null-control gate, paired deltas, trials, and provenance below

## Notes

- Grid resolution for this diagnostic package is **12×12** with 5-sample edge traces (sprint sketch suggested 64×64; denser grids remain available by editing the config once performance budgeting allows).
- V2.7 3R work remains held pending review of this dashboard.
