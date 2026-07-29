# Sprint Six status — Equivalence, Resolution, Statistical Trust

## Implemented

| Issue | Status | Notes |
| --- | --- | --- |
| S6-01 Equivalent-gain gearbox | Done | Affine `equivalent_gearbox` in `mechanisms/gearbox.py` |
| S6-02 Span matching | Done | `match_equivalent_gearbox(..., matching_rule="span")` |
| S6-03 TV / RMS matching | Done | `total_variation`, `rms_gain` |
| S6-04 Baseline registry | Done | `BASELINE_LABELS` / `baseline_label_for_*` |
| S6-05 Equivalence invariants | Done | `verify_span/tv/rms_match`, `verify_matched_graphs` |
| S6-06 Resolution sweep | Done | `run_sprint6` + `resolution_shapes` |
| S6-07 Scaling diagnostics | Done | Runtime / valid-node plots |
| S6-08 Production resolution | Done | ADR-013 + `select_production_resolution` |
| S6-09 High-res confirmation | Done | `high_resolution_confirmation` artifact |
| S6-10 Grid anisotropy note | Done | `GRID_ANISOTROPY_LIMITATION` in summary |
| S6-11 Sampling hierarchy | Done | Mechanism pair as independent unit |
| S6-12 Mechanism-level effects | Done | `mechanism_level_effects` |
| S6-13 Hierarchical bootstrap | Done | `metrics/hierarchical_bootstrap.py` |
| S6-14 Sample-size planning | Done | `required_mechanism_count` |
| S6-15 Staged MC configs | Done | Smoke YAML family + `sprint6` block |
| S6-16 Sequential precision | Done | `sequential_precision_report` |
| S6-17 Baseline matrix | Done | Equivalent / unit / four-bar via runner |
| S6-18 Matched-quantity tables | Done | `equivalence_summary` artifact |
| S6-19 Fixed sample bank | Done | `experiments/sample_bank.py` |
| S6-20 Pseudo-replication guard | Done | `assert_not_task_level_iid` |
| S6-21 Exclusion schema | Done | Coded `exclusions` JSON |
| S6-22 Stability plots | Done | Resolution + MC precision PNGs |

Schema: `SPRINT6_RESULT_SCHEMA_VERSION = "6.0.0"`.

ADRs: `ADR-012-equivalent-gain-matching.md`, `ADR-013-production-resolution.md`.

## Reproduce

```bash
# Full project printout (5 path samples + U/Q/Cartesian + expansions)
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint6.py \
  --config configs/sprint6.showcase.v1.yaml --mode full

MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint6.py \
  --config configs/sprint6.equivalence.smoke.v1.yaml

MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint6.py \
  --config configs/sprint6.resolution.smoke.v1.yaml --mode resolution
```

Open the consolidated HTML canvas at `results/<run_id>/index.html`
(written automatically; regenerable with
`scripts/generate_sprint6_canvas.py --run results/<run_id>`).

Showcase run: `results/sprint6_project_printout/index.html`.

## Locked policies

- Unit gearbox remains a separate identity baseline.
- Matching rule must appear in baseline labels (no bare “equivalent gearbox”).
- Mechanism pairs are the primary independent sampling unit; tasks are nested.
- Hierarchical bootstrap resamples mechanisms first, then tasks.
- Four-connected refinement is not isotropic (documented limitation).
