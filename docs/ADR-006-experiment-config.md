# ADR-006 — Experiment Configuration Schema

**Status:** Accepted

## Context

Version 1 Monte Carlo trials must be configuration driven (project plan M4).
Mechanism kinematics already serialize through the ADR-002 registry. Experiments
also need validated graph, limit, cost, algorithm, seed, and trial-sampling
fields so runs are reproducible and fail loudly on inconsistent inputs.

## Decision

Experiment configs are pydantic models in
`inequality_mechanisms.experiments.config`, loaded from YAML via
`load_experiment_config`.

### Top-level fields

| Field | Role |
| --- | --- |
| `seed` | Master RNG seed for mechanism sampling, task sampling, and randomized preimage policy. |
| `mechanisms.gearbox` | ADR-002 mechanism dict (`type` + parameters). |
| `mechanisms.fourbar` | Discriminated source: `mode: fixed` (mechanism dict) or `mode: population` (ADR-009 sampler fields). Legacy bare mechanism dicts coerce to `fixed`. |
| `graph` | Shared `PeriodicGrid2D` shape, optional ranges, wrap, `edge_samples`. Optional `match_valid_nodes` (IM-018 / ADR-010) refines a separate gearbox lattice over the Q box. |
| `limits` | Absolute shared output box (`lower`, `upper`) — **required for fixed mode; forbidden for population mode** (ADR-004 / ADR-009). |
| `cost` | Edge-cost family: `uniform`, `input_euclidean`, or `output_euclidean` (Sprint Four / S4-01). |
| `algorithms` | Forward solvers (`dijkstra`, `astar`) and optional `validate_heuristic` (reverse Dijkstra). |
| `trials` | `n_trials`, `min_output_separation`, `preimage_policy`, sampling caps, snap tolerance, `require_reachable`. |

Unknown keys are rejected (`extra="forbid"`). Gearbox dicts are checked for a
`type` key at schema time. Fixed four-bars are fully deserialized during model
validation so dimension mismatches with limits fail before any trial runs.
Population mode validates sampler bounds and requires `n_bars == 2`.

### Paired tasks (IM-015)

`generate_paired_tasks` samples matched output endpoints from valid gearbox
lattice nodes, stores selected discrete preimages for both mechanisms, and
records candidate counts. Four-bar preimages use continuous `inverse_output`
plus lattice snap with an output residual tolerance. In population mode the
pilot rebuilds graphs per trial before calling the generator (ADR-009).

### Failure behavior

| Condition | Behavior |
| --- | --- |
| Missing / invalid YAML root | `ValueError` |
| Schema / bound violations | `pydantic.ValidationError` |
| Unknown mechanism `type` | `MechanismRegistryError` during validation |
| Population mode with absolute `limits` | `ValidationError` |
| Fixed mode without `limits` | `ValidationError` |
| Exhausted task / mechanism sampling | `ValueError` from the task generator or pilot |

## Consequences

Benefits:

- one validated document drives pilot reproduction;
- mechanism kinematics stay on the ADR-002 path;
- population Monte Carlo and fixed demos share one schema;
- heuristic validation can be toggled without a separate config family.

Costs:

- adding a cost family or algorithm requires a schema (and usually an ADR) update;
- cost ablations share one physical input graph; only the edge metric changes (S4-01);
- native pilot mode assumes the same lattice geometry for both mechanisms.

Run-level persistence of config copies, seed, revision, environment, and
outputs is defined separately in ADR-007.
