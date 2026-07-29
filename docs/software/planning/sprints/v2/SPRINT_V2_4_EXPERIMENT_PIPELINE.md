# Sprint V2.4 — Versioned Experiment Pipeline

## Theme

> Make the new experiment impossible to run ambiguously.

## Objective

Add an explicit Version 2 configuration schema, task model, objective resolver, result schema, runner, CLI, provenance package, and compatibility layer while leaving Version 1 reproduction commands intact.

## Configuration contract

Version 2 configuration example:

```yaml
architecture_version: 2
result_schema_version: 2

planning_space: output

mechanisms:
  comparison: fourbar_vs_equivalent_affine_gearbox

branch:
  selection: monotonic_interval
  certification_samples_per_axis: 1025
  minimum_abs_gain: 0.05
  inverse_tolerance: 1.0e-9
  endpoint_margin_fraction: 0.02

sampling:
  domain: input
  shape: [64, 64]
  include_endpoints: true

objective:
  cost: output_euclidean
  heuristic: output_euclidean

edge_validation:
  samples: 17

tasks:
  source: fixed_output_pairs
  output_tolerance: 0.02

seed: 12345
trials: 20
```

## Issues

### V2-401 — Implement strict Version 2 config models

Create `experiments/v2_config.py` with typed dataclasses or the project's existing validation style.

Reject:

- missing or unsupported `architecture_version`;
- `planning_space != output` for Version 2;
- wrapped topology;
- full-cycle branch selection;
- output sampling without a unique branch inverse;
- unsupported cost/heuristic combinations;
- nonpositive dimensions or sample counts;
- branch and output-space dimension mismatch;
- Version 1-only preimage policy fields.

Do not add a new dependency solely for schema validation unless approved.

### V2-402 — Define Version 2 tasks in \(\mathcal Q\)

Initial tasks are requested output start/goal pairs:

```python
@dataclass(frozen=True)
class OutputTask:
    requested_start_q: NDArray[np.float64]
    requested_goal_q: NDArray[np.float64]
```

The task resolver must record:

- requested state;
- selected graph node;
- realized state;
- output residual vector and norm;
- corresponding actuator state;
- rejection reason if tolerance is exceeded.

There is no preimage selection policy in Version 2.

### V2-403 — Implement graph-specific task matching

For this sprint, use deterministic nearest-node matching in \(\mathcal Q\).

Requirements:

- tie-break by lowest node ID;
- match only valid nodes;
- configurable output residual tolerance;
- the same requested task reused across mechanisms and sampling modes;
- residuals reported separately for each graph;
- no silent resampling after a failed comparison condition.

Exact query overlays are deferred to Sprint V2.6.

### V2-404 — Extend the objective registry

Objectives operate on the embedded graph:

```python
def output_euclidean(graph, a, b) -> float:
    return graph.output_space.distance(graph.q_state(a), graph.q_state(b))

def input_euclidean(graph, a, b) -> float:
    return np.linalg.norm(graph.u_state(b) - graph.u_state(a))
```

Initial supported combinations:

| Cost | Heuristic |
| --- | --- |
| uniform | grid-step lower bound or zero |
| output_euclidean | output-space distance |
| input_euclidean | input-space distance or zero after admissibility validation |

A* must never reuse a heuristic intended for a different metric.

### V2-405 — Define result schema Version 2

Create a dedicated row model. Record all fields listed in `docs/software/PROJECT_PLAN.md`, including branch certificate, sampling domain, transition parameterization, endpoint residuals, spacing summaries, and code revision.

Store paths either:

- in trial rows for small fixtures; or
- in referenced sidecar files for larger runs.

The schema must be stable before the controlled study sprint.

### V2-406 — Implement Version 2 runner

Suggested module:

```text
src/inequality_mechanisms/experiments/v2_runner.py
```

Runner sequence:

1. load and validate config;
2. construct or sample mechanism pair;
3. select and certify branches;
4. construct matched affine gearbox branch;
5. construct requested graph(s);
6. resolve fixed output tasks;
7. resolve objective and heuristic;
8. run Dijkstra and/or A*;
9. compute path metrics in \(\mathcal U\), \(\mathcal Q\), and \(\mathcal X\);
10. write immutable run package.

### V2-407 — Add CLI and reproducibility package

Add:

```bash
python scripts/run_v2_experiment.py --config configs/v2/controlled_2r.yaml
```

Run package:

```text
results/<run_id>/
├── config.yaml
├── manifest.json
├── trials.jsonl
├── summary.csv
├── failures.jsonl
├── branches/
├── diagnostics/
└── figures/
```

Manifest includes environment, dependency versions, code revision, dirty-tree flag, architecture version, and result schema version.

### V2-408 — Preserve Version 1 commands

Add regression tests or smoke tests verifying existing Version 1 config loading and reproduction entry points still resolve to Version 1 code.

Do not route legacy files through the Version 2 runner.

### V2-409 — End-to-end null-control search test

Run two mechanisms on one shared uniform-\(\mathcal Q\) graph with output-distance objective.

Assert exact equality of:

- selected start/goal node IDs;
- costs;
- paths;
- expansions;
- generated/stale counts;
- expanded order when recorded.

This test is a hard gate for Sprint V2.5.

## Expected file changes

```text
src/inequality_mechanisms/experiments/v2_config.py
src/inequality_mechanisms/experiments/v2_tasks.py
src/inequality_mechanisms/experiments/v2_results.py
src/inequality_mechanisms/experiments/v2_runner.py
src/inequality_mechanisms/search/objectives.py
scripts/run_v2_experiment.py
configs/v2/...
tests/experiments_v2/...
```

## Non-goals

- no large Monte Carlo;
- no exact overlay nodes;
- no capability costs beyond input/output distance;
- no 3R;
- no deletion or migration of Version 1 result packages.

## Recommended pull requests

1. **PR V2.4-A:** strict config and compatibility tests.
2. **PR V2.4-B:** task model and objective registry.
3. **PR V2.4-C:** result schema and runner.
4. **PR V2.4-D:** CLI, run package, null-control end-to-end test.

## Verification

```bash
pytest tests/experiments_v2
pytest tests/golden_v1
python scripts/run_v2_experiment.py --config configs/v2/smoke.yaml
pytest
ruff check .
ruff format --check .
mypy src
```

## Sprint exit criteria

1. Version 2 configs are explicit and reject mixed semantics.
2. Tasks are specified in \(\mathcal Q\) with no preimage policy.
3. Endpoint residuals are stored and enforced.
4. One command produces an immutable Version 2 smoke-run package.
5. The full search-level null-control invariant passes.
6. Existing Version 1 commands and golden fixtures still pass.

## Cursor starter prompt

```text
Implement Sprint V2.4 only. Add a strict architecture_version: 2 config path,
Q-space task model, explicit objective resolver, Version 2 result schema, runner,
and CLI. Keep Version 1 loading and commands separate and unchanged. Use
nearest-valid-Q-node matching with deterministic tie-breaking and explicit
residual rejection; do not implement query overlays. Add a hard end-to-end null
control test using one shared uniform-Q graph. Run Version 2 tests, Version 1
golden tests, a smoke CLI run, and full CI.
```
