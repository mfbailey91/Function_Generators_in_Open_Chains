# Sprint Five status — Path Quality and Trajectory Character

## Implemented

| Issue | Status | Notes |
| --- | --- | --- |
| S5-01 Path lengths | Done | Hardened `path_metrics.py`; `L_Q` via `OutputSpace.distance`; conventions in `PATH_LENGTH_CONVENTIONS` |
| S5-02 Directness | Done | `path_quality.py`; undefined → `None` + `directness_defined_*=false` |
| S5-03 Cumulative turning | Done | `T_Q`, `T_X` primary; zero segments skipped; range `[0, π]` |
| S5-04 Self-intersections | Done | Nonadjacent segment crossings; collinear overlap counted; atol `1e-12` |
| S5-05 Near-revisits | Done | Point-to-point V1; `PathQualityConfig` on experiment YAML |
| S5-06 Cards | Done | `visualization/path_quality.py` + deterministic selection |
| S5-07 Equal-cost paths | Done | `metrics/equal_cost_paths.py`; heap tie-break documented |
| S5-08 Paired study | Done | `run_sprint5` + smoke/factorial configs |
| S5-09 Bootstrap | Done | `bootstrap_path_quality_metrics` with undefined/sparse counts |

Schema: `SPRINT5_RESULT_SCHEMA_VERSION = "5.0.0"`.

## Reproduce

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint5.py \
  --config configs/sprint5.smoke.v1.yaml

MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint5.py \
  --config configs/sprint5.factorial.v1.yaml
```

Open the consolidated HTML canvas at `results/<run_id>/index.html`
(written automatically; regenerable with
`scripts/generate_sprint5_canvas.py --run results/<run_id>`).

## Locked policies

- Collinear overlapping nonadjacent segments count as one intersection each pair.
- Ordinary adjacent segment pairs are excluded.
- Directness denominator atol: `1e-12`.
- No composite path-quality score.
