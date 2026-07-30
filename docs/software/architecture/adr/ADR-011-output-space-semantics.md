# ADR-011 — Output Configuration Space Semantics (IM-032)

**Status:** Accepted

## Context

Version 1 search identity lives in input space \(\mathcal U\) (ADR-001). Shared
limits, edge costs, heuristics, and matched-task residuals live in output
configuration space \(\mathcal Q\). Until Sprint Two, the software treated
output coordinates as raw NumPy vectors and subtracted them directly. Four-bar
forward maps returned principal-value follower angles while follower-range
calculations used continuous unwrapping. That mismatch admits false
near-\(2\pi\) edge costs and discontinuous plotted paths when a smooth rocker
curve crosses the principal-angle seam.

A rocker does not complete a full revolution. Crossing the upper shared joint
limit and reappearing at the lower limit is physically invalid, so \(\mathcal Q\)
must not use a shortest-angle metric for the Sprint Two mechanism family.

See `docs/SPRINT_TWO_BACKLOG.md` for the Sprint Two working design.

## Decision

### Topology of \(\mathcal Q\)

For the Sprint Two study,

\[
\mathcal Q =
[q_{1,\min},q_{1,\max}]
\times
[q_{2,\min},q_{2,\max}]
\subset \mathbb R^2
\]

with each axis a **bounded revolute** chart (not a periodic \(S^1\)). Input
periodicity on crank axes remains independent (ADR-001, ADR-003).

Require

\[
0 < q_{i,\max}-q_{i,\min} < 2\pi
\]

for every bounded revolute output axis. A future full-rotation joint must use a
distinct periodic axis type.

### Lifted-angle representation

With chart center \(q_c=(q_{\min}+q_{\max})/2\),

\[
\operatorname{lift}(\theta)
=
q_c +
\operatorname{wrap}_{(-\pi,\pi]}
(\theta-q_c).
\]

Mechanisms may emit raw Freudenstein (or gearbox) angles. The shared output
space **canonicalizes** those values into the trial chart before limits,
costs, heuristics, residuals, serialization, or plots consume them.

### Displacement and distance

\[
\Delta_{\mathcal Q}(q_a,q_b)
=
\operatorname{canonicalize}(q_b)
-
\operatorname{canonicalize}(q_a),
\qquad
d_{\mathcal Q}(q_a,q_b)
=
\|\Delta_{\mathcal Q}(q_a,q_b)\|_2.
\]

Raw principal-angle subtraction and unconditional shortest-angle wrapping are
prohibited in output-space costs, heuristics, task residuals, and limit checks.

Default Version 1 edge cost remains (ADR-005, updated):

\[
c(u_a,u_b)
=
d_{\mathcal Q}\bigl(g(u_a),g(u_b)\bigr).
\]

### Ownership

| Owner | Responsibility |
| --- | --- |
| `Mechanism` | Raw map \(q_{\mathrm{raw}}=g_m(u)\), assembly, Jacobian, inverse in raw or chart-compatible form |
| `OutputSpace` | Per-axis topology, canonicalize, displacement, distance, contains, serialization |
| `OutputJointLimits` | Closed box bounds; membership is evaluated on **canonicalized** coordinates |
| `ConstrainedInputGraph` | Graph-facing boundary (IM-042): `raw_output`, `output`, `output_displacement`. Downstream validity consumers, edge costs, heuristics, tasks, residuals, and plots that operate on a constructed graph must use this path rather than calling `mechanism.input_to_output()` directly. |

Construction helpers (`configuration_is_valid`) and graph-free unit-test helpers may call the raw map only when no graph instance exists; those call sites must be explicitly labeled. See `docs/notes/IM-043-input-to-output-audit.md`.

Version 1 implements only bounded revolute axes. The software interface must
permit future mixtures of bounded revolute, periodic revolute, and prismatic
axes without changing search identity in \(\mathcal U\).

### Consequences for existing ADRs

- **ADR-004:** Shared limits still use one closed box per trial; membership
  checks canonicalize through `OutputSpace` first.
- **ADR-005:** Output Euclidean cost and A* heuristic use
  \(d_{\mathcal Q}\), not raw subtraction. Custom costs must not silently reuse
  the default output heuristic (IM-035).
- **ADR-003:** Algebraic Freudenstein branches are unchanged; the lift is an
  output-chart layer after the selected-branch solve.
- **ADR-009 / ADR-010:** Population follower ranges define the shared chart
  bounds; equal-node gearbox lattices remain over that same Q box.

## Failure behavior

| Condition | Behavior |
| --- | --- |
| Axis span \(\le 0\) or \(\ge 2\pi\) (bounded revolute) | `ValueError` |
| Dimension mismatch between space and query | `ValueError` |
| Non-finite coordinates | `ValueError` |
| Mechanism inventing its own output-angle convention for costs | Disallowed; costs go through `OutputSpace` |

## Consequences

Benefits:

- seam-crossing follower paths stay continuous in \(\mathcal Q\);
- gearbox and four-bar share one comparison chart;
- no circular shortcuts across bounded rocker limits;
- future axis types can extend the same interface.

Costs:

- every consumer of output differences must take an `OutputSpace`;
- four-bar forward/inverse/range and task endpoints must stay trial-consistent
  on the lifted chart (IM-034).
