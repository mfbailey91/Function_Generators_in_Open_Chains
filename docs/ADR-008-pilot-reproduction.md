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
| `found` | Whether a finite-cost path was returned |
| `n_expanded`, `n_generated`, `n_stale`, `n_path_edges`, `cost` | Search instrumentation (ADR-005) |
| `n_valid_nodes` | Denominator for normalized expansion |
| `rho_expanded` | `N_expanded / N_valid_nodes` when `found`, else `null` |
| `failure_reason` | e.g. `unreachable`, or heuristic validation message |
| `preimages`, `q_start`, `q_goal` | Task identity |
| `fourbar_mode` | `fixed` or `population` |
| `fourbar_lengths` | Per-axis `(a,b,c,d)` for the trial’s four-bar |
| `limits` | Shared `{lower, upper}` used for that trial (follower ranges in population mode) |

Unreachable searches are **preserved** as rows with `found=false`; they are
excluded from expansion plot series.

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

## Consequences

Benefits:

- config → run → plots is auditable and repeatable;
- raw vs normalized expansions separate graph-size confounding from search effort;
- failed trials remain machine-readable.

Costs:

- matplotlib is required for reproduction even when only tabular output is needed;
- population mode rebuilds graphs per trial under four-bar-derived limits (ADR-009);
- fixed mode still uses one mechanism pair and shared lattice geometry (ADR-006).
