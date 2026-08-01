# ADR-017 — Shared-Q Planning with Normalized Q/U Cost

**Status:** Accepted
**Architecture versions:** Version 2
**Related:** ADR-012, ADR-014, ADR-015, ADR-016

## Context

Version 2 permits output-state planning on certified monotonic mechanism branches.
A common uniform-\(\mathcal Q\) graph removes mechanism-dependent node placement
from the comparison, but a pure output-distance objective also removes the
transmission from the search problem. To compare how different transmissions
value the same possible arm motions, the graph must retain each mechanism's
unique actuator realization and include actuator-side motion in the edge cost.

A four-bar and its linear control must also have comparable overall scale. ADR-012
already defines span matching on monotonic branches. This decision applies that
control in the inverse direction used by a shared output graph.

## Decision

### Shared output topology

For each accepted mechanism pair, construct one common uniform output lattice:

\[
G_Q=(V_Q,E_Q).
\]

The four-bar and span-matched gearbox must share:

- output bounds;
- node IDs and output coordinates;
- nominal adjacency;
- exact start and goal query states;
- output-linear transition provenance.

Each mechanism attaches its own unique actuator realization:

\[
\mathbf u_m(\mathbf q)=g_m^{-1}(\mathbf q).
\]

A mismatch in accepted node or edge topology is an invariant failure for this
study, not an experimental result to average over.

### Span-matched affine gearbox

For each axis of a certified monotonic four-bar branch,

\[
r_{\mathrm{eq}}
=
\frac{q_{\max}-q_{\min}}
{u_{\max}-u_{\min}}.
\]

Use the affine map

\[
q
=
q_{\min}
+
r_{\mathrm{eq}}(u-u_{\min}),
\]

with inverse

\[
u_{\mathrm{GB}}(q)
=
u_{\min}
+
\frac{q-q_{\min}}{r_{\mathrm{eq}}}.
\]

The matched gearbox therefore covers the same output interval with the same
actuator span as the four-bar while replacing its variable gain with one
constant secant gain. Plots and tables must use the label
`span_matched_gearbox`.

### Normalized additive objective

For an edge trace \(e\), calculate output and actuator arc lengths:

\[
d_Q(e)=\int_e \lVert d\mathbf q\rVert_2,
\qquad
d_U^{(m)}(e)=\int_e \lVert d\mathbf u_m\rVert_2.
\]

Use pair-level characteristic scales

\[
s_Q
=
\left\lVert
\mathbf q_{\max}-\mathbf q_{\min}
\right\rVert_2,
\qquad
s_U
=
\left\lVert
\mathbf u_{\max}-\mathbf u_{\min}
\right\rVert_2.
\]

Because the linear control is span matched, \(s_U\) is shared by both mechanisms
in a pair. The edge objective is

\[
c_{\alpha}^{(m)}(e)
=
\alpha\frac{d_Q(e)}{s_Q}
+
(1-\alpha)\frac{d_U^{(m)}(e)}{s_U},
\qquad
0\le\alpha\le1.
\]

Required study weights are

\[
\alpha\in\{1.0,0.75,0.5,0.25,0.0\}.
\]

The primary mixed condition is \(\alpha=0.5\). The endpoints are controls:

- \(\alpha=1\): pure output-distance null control;
- \(\alpha=0\): pure actuator-distance comparison.

Store the unnormalized \(d_Q\) and \(d_U\), both normalized components, and the
combined cost. A favorable combined score must never be reported without its
components.

### Search and heuristic policy

Dijkstra is the reference algorithm for every weight. A* may use

\[
h_{\alpha}^{(m)}(n)
=
\alpha
\frac{\lVert \mathbf q_n-\mathbf q_g\rVert_2}{s_Q}
+
(1-\alpha)
\frac{\lVert \mathbf u_n^{(m)}-\mathbf u_g^{(m)}\rVert_2}{s_U},
\]

only after admissibility is checked against exact reverse distances on
representative fixtures.

## Consequences

Benefits:

- the arm configurations and nominal graph topology are controlled exactly;
- the transmission enters through a physically interpretable actuator embedding;
- scale and nonlinearity are separated by span matching;
- pure output, pure actuator, and mixed objectives belong to one explicit family.

Costs:

- the study is limited to certified invertible branches;
- normalization choices become part of the experiment contract;
- the dashboard and result schema must preserve component costs and provenance;
- full-cycle or multi-preimage mechanisms still require Version 1 or a future
  lifted output state.

## Implementation and test consequences

- Add a registered normalized `q_u_blend` objective with explicit `alpha`, `s_q`,
  and `s_u` metadata.
- Reuse output-linear transition traces for both mechanisms.
- Assert identical output node IDs, coordinates, adjacency, query connectivity,
  and reachable topology within every pair.
- Assert forward/inverse residuals for four-bar and gearbox mappings.
- Preserve existing pure `output_euclidean` and `input_euclidean` objectives.
- Add affine and nonlinear fixtures for component-cost and heuristic tests.
