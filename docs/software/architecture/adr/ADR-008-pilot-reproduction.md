# ADR-008 — Pilot Reproduction Outputs

**Status:** Accepted

## Context

Project plan M4 requires one command to reproduce paired expansion plots and a
results table from a versioned config. IM-014–016 supply config, paired tasks,
and the run registry; IM-017 defines the trial schema, normalized expansion
metric, and figure contract.

## Decision

### Runner

`inequality_mechanisms.experiments.pilot.run_pilot` (CLI:
`scripts/reproduce_pilot.py`) loads an `ExperimentConfig`, creates a registry
run under `results/<run_id>/`, executes Dijkstra and/or A* on matched gearbox
and four-bar preimages, then writes analysis artifacts. Completed runs remain
immutable (ADR-007).

### Trial JSONL (`outputs/trials.jsonl`)

One record per `(trial_index, mechanism, algorithm)` with at least:

| Field | Role |
| --- | --- |
| `result_schema_version` | Trial schema version (`"4.0.0"` P0; `"4.1.0"` P1 adds runtime / β / reachable / edge-cost variance; `"5.0.0"` Sprint Five path-quality fields) |
| `found` | Whether a finite-cost path was returned |
| `n_expanded`, `n_generated`, `n_stale`, `n_path_edges` | Search instrumentation (ADR-005) |
| `cost_type`, `heuristic_type` | Resolved planning objective (S4-01 / S4-02) |
| `optimal_cost` | \(C^*\) under the selected edge metric |
| `cost` | Alias of `optimal_cost` (backward compatible) |
| `path_length_u`, `path_length_q`, `path_length_x` | Path lengths in \(\mathcal U\), \(\mathcal Q\), \(\mathcal X\) (S4-03 / S5-01) |
| `directness_ratio_u/q/x`, `directness_defined_u/q/x` | Detour ratios \(R = L / d(\mathrm{start},\mathrm{goal})\); undefined when endpoint displacement is degenerate (S5-02) |
| `cumulative_turning_q`, `cumulative_turning_x` | Sum of polyline turning angles in \([0,\pi]\) (S5-03) |
| `self_intersections_q`, `self_intersections_x` | Nonadjacent projected segment crossings (S5-04) |
| `near_revisit_distance_q/x`, `near_revisit_count_q/x` | Point-to-point nonlocal revisit metrics (S5-05) |
| `runtime_s` | Wall-clock search time in seconds (P1) |
| `n_reachable_nodes`, `beta`, `eta_reachable` | Reachable count and goal-cost-ball fractions (S4-08) |
| `edge_cost_variance` | Variance of edge weights under the selected cost (S4-07/S4-09) |
| `n_valid_nodes` | Denominator for normalized expansion |
| `rho_expanded` | `N_expanded / N_valid_nodes` when `found`, else `null` |
| `failure_reason` | e.g. `unreachable`, or heuristic validation message |
| `heuristic_validation`, `heuristic_quality` | Optional reverse-search diagnostics when enabled (S4-04) |
| `preimages`, `q_start`, `q_goal` | Task identity |
| `fourbar_mode` | `fixed` or `population` |
| `fourbar_lengths` | Per-axis `(a,b,c,d)` for the trial’s four-bar |
| `limits` | Shared `{lower, upper}` used for that trial (follower ranges in population mode) |

Under each cost type, solved paths satisfy (within numerical tolerance):
`uniform` ⇒ \(C^*=N_{\mathrm{edges}}\); `input_euclidean` ⇒ \(C^*=L_U\);
`output_euclidean` ⇒ \(C^*=L_Q\).

Unreachable searches are **preserved** as rows with `found=false`; they are
excluded from expansion plot series. Cost and heuristic names remain present
on failed rows.

### Normalized expansion

$$
\rho_{\mathrm{expanded}} = \frac{N_{\mathrm{expanded}}}{N_{\mathrm{valid\ nodes}}}
$$

Paired log-ratio (successful pairs only, positive counts):

$$
\log\bigl(N_{\mathrm{expanded,4R}} / N_{\mathrm{expanded,gear}}\bigr)
$$

### Figures

Registered under `outputs/`:

- `expansions_raw.png` — boxplot of raw expansions (algorithm × mechanism)
- `expansions_normalized.png` — boxplot of $\rho_{\mathrm{expanded}}$
- `expansions_ratio.png` — overlaid histogram of paired log-ratios

Analysis loads trial JSONL and does not rewrite it. Matplotlib is a core
dependency so the one-command path can emit PNGs without an optional extra.

### Summary

`summary.json` plus `summary_table.csv` aggregate medians, mean $\rho$,
unreachable counts, and paired-ratio statistics.

### Sprint Five path-quality runner

`inequality_mechanisms.experiments.sprint5.run_sprint5` (CLI:
`scripts/reproduce_sprint5.py`) reuses the Sprint Four factorial design and
writes schema `"5.0.0"` trial rows with path-quality fields. Additional
artifacts include:

- `outputs/equal_cost_path_degeneracy.json` — Dijkstra vs A* secondary-path
  comparison under equal optimal cost (S5-07);
- `path_quality/` — deterministic representative diagnostic cards (S5-06);
- paired path-quality figures and summary CSVs (S5-08);
- `bootstrap_cis.json` with `path_quality` intervals and undefined counts
  (S5-09).

Metric tolerances and conventions are stored in `graph_meta.json` /
`metric_configuration.json`. Directness ratios use sentinel `null` with
`directness_defined_*=false` when the endpoint displacement is at most
`1e-12`. Self-intersection absolute tolerance is `1e-12`. Near-revisits are
point-to-point with config exclusion window and thresholds. No composite
path-quality score is defined.

## Consequences

Benefits:

- config → run → plots is auditable and repeatable;
- raw vs normalized expansions separate graph-size confounding from search effort;
- failed trials remain machine-readable;
- Sprint Five evaluates path quality separately in \(\mathcal U\), \(\mathcal Q\),
  and \(\mathcal X\) without collapsing to one ranking.

Costs:

- matplotlib is required for reproduction even when only tabular output is needed;
- population mode rebuilds graphs per trial under four-bar-derived limits (ADR-009);
- fixed mode still uses one mechanism pair and shared lattice geometry (ADR-006).
