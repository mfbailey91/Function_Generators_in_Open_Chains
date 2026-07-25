# ADR-004 — Shared Output Limits and Edge Validation

**Status:** Accepted

## Context

Version 1 compares gearboxes and four-bars under matched planning tasks. Fairness requires the same follower joint limits for every mechanism. Limits act in output joint space \(\mathcal Q\), while search identity remains in input space \(\mathcal U\) (ADR-001). Assembly checks stay separate from limit checks (ADR-002).

Endpoint-only edge checks can create false connectivity when a nonlinear map leaves the limit box or assembly domain between neighboring samples.

## Decision

### Shared limits

- Represent limits as a closed axis-aligned box `OutputJointLimits` in
  `inequality_mechanisms.spaces.limits`.
- A configuration \(u\) is **node-valid** iff `mechanism.valid_input(u)` and
  \(g(u)\) lies in the limit box.
- The same `OutputJointLimits` instance is applied to gearbox and four-bar
  graphs in a paired trial.
- For population Monte Carlo (ADR-009), that shared box is the sampled
  four-bar’s selected-branch follower range on each axis—not a hand-chosen
  absolute window.

### Edge validation

- Neighbor edges are checked along the **short** input segment
  \(u(s)=(1-s)u_a + s\cdot\Delta_{\mathrm{short}}(u_b-u_a)\), \(s\in[0,1]\).
- On periodic axes the short displacement wraps with period \(2\pi\).
- Sample the segment (including endpoints). Reject the edge if any sample fails
  node validity.
- `ConstrainedInputGraph` filters `PeriodicGrid2D` nodes and edges with these
  rules.

### Failure behavior

| Condition | Behavior |
| --- | --- |
| `limits.dim != mechanism.output_dim` | `ValueError` |
| Malformed limit bounds (`upper <= lower`, non-finite) | `ValueError` |
| `edge_samples < 2` | `ValueError` |
| Invalid node queried for neighbors | empty neighbor list |

## Consequences

Benefits:

- gearbox and four-bar share one constraint object in \(\mathcal Q\);
- wrapping edges use the physically short crank step, not the long chord;
- interior violations cannot silently bridge disconnected valid regions.

Costs:

- denser sampling raises graph-build cost;
- a finite sample count can still miss a measure-zero or narrow violation
  between samples (accepted Version 1 approximation; raise `edge_samples` if
  needed).
