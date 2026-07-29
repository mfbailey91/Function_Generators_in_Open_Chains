# ADR-013 — Production Graph Resolution Selection

**Status:** Accepted

## Context

Graph resolution affects valid-node counts, endpoint snapping, edge
validation, connectivity, path cost, expansions, and runtime. Sprint Six
calibrates a production \(n \times n\) lattice before claiming Monte Carlo
effects are resolution-stable.

## Decision

### Candidate resolutions

Default sweep:

\[
\{32, 48, 64, 96, 128\}
\]

when computationally practical. Smoke configs may use a reduced set.

### Primary effect

\[
d = \log\left(
\frac{N_{\mathrm{expanded,fb}}+1}{N_{\mathrm{expanded,gb}}+1}
\right)
\]

aggregated at the mechanism level when hierarchical sampling is used.

### Acceptance criteria (project decisions)

Configured under `sprint6`:

| Field | Default | Meaning |
| --- | --- | --- |
| `max_relative_effect_change` | `0.05` | Relative change vs next higher resolution |
| `require_sign_stability` | `true` | Sign of primary effect unchanged at next higher \(n\) |
| `require_component_stability` | `true` | Connected-component count stable |
| `require_task_feasibility_stability` | `true` | Task acceptance rate stable |

Select the **coarsest** resolution that meets all enabled criteria against the
next higher candidate. Record the decision and thresholds in run metadata.

### Grid anisotropy limitation

Four-connected adjacency permits axis-aligned moves only. Refinement reduces
step size but does **not** remove intrinsic directional bias. An
eight-connected ablation is out of scope for Sprint Six. Runs set
`sprint6.grid_anisotropy_acknowledged: true` and store the limitation string
in summary metadata.

## Consequences

- Production resolution is a documented project decision, not an implicit
  default.
- High-resolution confirmation (S6-09) reuses a representative subset at the
  next higher practical \(n\) after the main study.
