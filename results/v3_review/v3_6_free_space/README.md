# Version 3 review snapshot — V3.6 free-space evidence

This directory is a **bounded free-space planner evidence package**, not a population study, Monte Carlo result, or obstacle campaign.

- Code revision: `f1f3ab9a5edd259cc26deae514695f3c19cd45b3`
- Generated UTC: `2026-08-07T08:44:55Z`
- Bank: `free_space_planar2r_v1`
- Seed: `7`
- OMPL available: `True`
- OMPL version: `2.0.1`
- OMPL solve budget: `2.0` s
- Rows: `238` (17 tasks × 2 mechanisms)

## Reproducibility note

Native stochastic planners reuse V3.4 `SMOKE_SEED` (7). OMPL adapters declare `reproducible_with_seed=False`: in-process seed setting is process-global best effort (RNG already started warnings are expected on multi-query runs). Frozen OMPL repetitions for strict comparison should use process isolation.

## Status counts

```json
{
  "invalid": 24,
  "success": 207
}
```

## Skip counts

```json
{
  "no_goal_candidate_for_lattice": 7
}
```

## Planner success means (success rows only)

| planner | n_success | mean objective_cost | mean query_time_s |
| --- | ---: | ---: | ---: |
| `input_linear` | 30 | 1.388 | 0.004 |
| `lattice_dijkstra_eight_integrated` | 27 | 1.67 | 3.143 |
| `ompl_prm` | 30 | 1.388 | 1.805 |
| `ompl_rrt_connect` | 30 | 1.425 | 0.004 |
| `output_linear` | 30 | 1.389 | 0.044 |
| `prm` | 30 | 1.388 | 0.106 |
| `rrt_connect` | 30 | 1.568 | 0.004 |

Files:

- `rows.json` — row-level evidence
- `manifest.json` — run metadata
- `summary.json` — stratum / planner aggregates
- `V3_6_FREE_SPACE_EVIDENCE.html` — print-ready summary

Regenerate with:

```bash
PYTHONPATH=src:. python scripts/run_v3_6_free_space_evidence.py
```

Prefer the OMPL-enabled interpreter (e.g. `.conda-ompl`) when publishing OMPL rows.
