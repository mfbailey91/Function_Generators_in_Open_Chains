# Version 3 review snapshot — corrected V3.6 free-space evidence

This is the **v2 corrective closeout candidate** for Sprint V3.6. The v1 artifact is retained as pilot provenance.

- Implementation revision: `a5a682cc59e88d042b38c432134a882e5b24bc28`
- Generated UTC: `2026-08-07T10:27:46Z`
- Bank: `free_space_planar2r_v2`
- Frozen stochastic seeds: `[7, 29, 61]`
- OMPL process isolation: `True`
- Rows: `510`

## Interpretation

All paired tasks use the same resolved `start_q` and Cartesian start tip. The physical Cartesian disk remains the goal predicate, while every planner receives the same frozen center + near-boundary representation.

In this unconstrained convex free-space baseline, valid represented goals are expected to be input-linearly direct. The primary question is therefore planner representation/optimality relative to the direct represented-goal reference, not whether nonlocal routing is necessary.

Primary cross-family timing is `total_wall_time_s`; query-only timing is reported as a secondary implementation diagnostic.

## Planner summary

| planner | n success | mean cost | mean subopt | mean total wall s | mean ΔJ F-G |
| --- | ---: | ---: | ---: | ---: | ---: |
| `input_linear` | 30 | 1.1915 | 0 | 0.027895 | -0.24753 |
| `lattice_dijkstra_eight_integrated` | 30 | 1.2686 | 0.077099 | 27.986 | -0.26164 |
| `ompl_prm` | 90 | 1.1915 | -1.3693e-16 | 3.6988 | -0.24753 |
| `ompl_rrt_connect` | 90 | 1.428 | 0.23647 | 0.026198 | -0.24736 |
| `output_linear` | 30 | 1.1919 | 0.00036886 | 0.38113 | -0.24679 |
| `prm` | 90 | 1.1917 | 0.00012117 | 0.78774 | -0.24777 |
| `rrt_connect` | 90 | 1.4009 | 0.20939 | 0.01118 | -0.26435 |

Files:

- `resolved_bank.json` — audited shared starts and frozen goal points
- `rows.json` — row-level evidence
- `manifest.json` — implementation revision and run contract
- `summary.json` — paired/suboptimality aggregates
- `V3_6_FREE_SPACE_EVIDENCE_V2.html` — GitHub/print review

This remains bounded evidence, not a population estimand or Monte Carlo campaign.
