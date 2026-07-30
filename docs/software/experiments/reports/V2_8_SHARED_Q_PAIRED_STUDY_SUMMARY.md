# Sprint V2.8 evidence summary — Shared-Q paired study

**Run id:** `v2_8_shared_q_paired_2r`  
**Package:** `results/v2_8_shared_q_paired_2r/`  
**Config:** `configs/v2/shared_q_paired_2r.yaml`  
**Cardinality:** 5 pairs × 3 tasks × 5 alphas × 2 mechanisms = **150** Dijkstra trials; **75** paired comparisons; **0** failures.

## Null control

At \(\alpha=1\) (pure output distance) every pair-task case matched on cost, path, and expansions (**15/15**). Unequal feasible nodes were intersected into a shared validity mask before search so topology identity is an invariant, not an average.

## Objective-weight effects

| \(\alpha\) | Identical Q-paths | Mean \|cost Δ\| |
| --- | ---: | ---: |
| 1.0 | 15/15 | 0 |
| 0.75 | 3/15 | 0.031 |
| 0.5 | 1/15 | 0.062 |
| 0.25 | 2/15 | 0.092 |
| 0.0 | 3/15 | 0.123 |

Path divergence appears as soon as actuator weight is introduced. Cost deltas grow monotonically as \(\alpha\) decreases toward pure actuator travel.

## Mechanism nonlinearity

Divergence onset (largest \(\alpha\) with non-identical paths) is typically **0.75** across pairs. Asymmetric / joint-distinct pairs (`pair_04`, `pair_05`) show some task-dependent later onset (0.5 on selected tasks), consistent with axis-specific transmission structure.

## Task dependence

At the primary mixed weight \(\alpha=0.5\):

- `cross_range`: 0/5 identical paths  
- `joint1_dominant`: 1/5 identical  
- `joint2_dominant`: 0/5 identical  

Long diagonals and joint-2-dominant queries expose transmission differences more than the milder joint-1-dominant set in this frozen fixture catalog.

## Search effort vs path quality

Paired comparison rows record expansion deltas, \(L_U/L_Q/L_X\), node/edge Jaccard overlap, Cartesian separation, and actuator-travel ratios. Expansion changes and path changes do not move in lockstep: some cases diverge in selected Q-path while expansion counts remain close. Fewer expansions alone is not treated as a quality claim (sprint non-goal).

## Dashboard

Open `results/v2_8_shared_q_paired_2r/index.html` locally for task-set sections, pair columns, alpha panels, paired deltas, null-control status, and provenance.

## Notes

- Grid resolution for this diagnostic package is **12×12** with 5-sample edge traces (sprint sketch suggested 64×64; denser grids remain available by editing the config once performance budgeting allows).
- V2.7 3R work remains held pending review of this dashboard.
