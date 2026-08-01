# Sprint V2.8 — Shared-Q Paired Mechanism Study

## Theme

> Hold the possible arm motions fixed, then observe how different transmissions value and traverse them.

## Objective

Turn the Version 2 shared-output architecture into a focused, inspectable study of
five monotonic four-bar arms and five span-matched gearbox controls. Evaluate the
same five mechanism pairs across three deterministic start-goal task sets, apply a
normalized blend of output and actuator travel, and generate one HTML dashboard
that shows the complete planning story in \(\mathcal U\), \(\mathcal Q\), and
\(\mathcal X\).

## Sprint question

> When a four-bar arm and a span-matched gearbox arm share exactly the same output-state graph, how do transmission-dependent actuator costs change search effort and the selected output and Cartesian paths across different tasks?

## Narrative role

This sprint implements the **planning-control view** that follows the paper's
**mechanism view**:

1. Uniform \(\mathcal U\) mapped into \(\mathcal Q\) explains what the function
   generator physically generates.
2. Uniform \(\mathcal Q\) mapped into mechanism-specific \(\mathcal U\) provides
   the apples-to-apples planning comparison.

A uniform output graph initially obscures the mechanism because all arms appear
to have the same nodes. The mechanism re-enters through the inverse map,
transition realization, and edge cost. Without those fields, the planner silently
models every transmission as the unit gearbox.

## Accepted scope decisions

- Use **certified monotonic branches only**.
- Freeze **five 2R four-bar arms**. Each arm contains one accepted monotonic
  four-bar branch per joint.
- Pair each arm with its own **span-matched affine gearbox arm** under ADR-012.
- Reuse those same five mechanism pairs across **three task sets** with different
  exact start and goal states.
- Use one common uniform-\(\mathcal Q\) graph within each mechanism pair.
- Use the normalized additive \(Q/U\) objective in ADR-017.
- Keep Sprint V2.7 3R work held.

## Experiment cardinality

The fixed diagnostic study contains:

- 5 mechanism pairs;
- 3 task sets;
- 5 cost weights;
- 2 mechanisms per pair.

This produces 15 pair-task cases and 150 reference Dijkstra runs:

\[
5\times3\times5\times2=150.
\]

A* runs are additional and are permitted only after the blended heuristic passes
admissibility tests.

## Mechanism pairs

Each pair \(p\in\{1,\ldots,5\}\) contains:

\[
\left(
 m_{\mathrm{FB},p},
 m_{\mathrm{GB},p}
\right).
\]

The four-bar arm must pass the existing branch certificate for both axes. The
gearbox is materialized from that branch using per-axis span gain:

\[
r_{\mathrm{eq},i}
=
\frac{q_{i,\max}-q_{i,\min}}
{u_{i,\max}-u_{i,\min}}.
\]

Its inverse embedding on the shared output graph is

\[
u_{\mathrm{GB},i}(q_i)
=
u_{i,\min}
+
\frac{q_i-q_{i,\min}}{r_{\mathrm{eq},i}}.
\]

The five pairs should span a deliberately interpretable range of nonlinearity:

1. mild variation in gain;
2. moderate variation;
3. strong but well-conditioned variation;
4. asymmetric gain distribution across the operating branch;
5. distinct behavior between joint 1 and joint 2.

Selection is deterministic and versioned. Do not redraw mechanisms during the
three task sets.

## Three task sets

Task states are exact query overlays and are specified in normalized coordinates
inside each pair's shared output box. The initial versioned templates are:

| Task | Start fraction | Goal fraction | Purpose |
| --- | --- | --- | --- |
| T1 — cross-range | \((0.15,0.20)\) | \((0.85,0.80)\) | long diagonal movement through both axes |
| T2 — joint-1 dominant | \((0.15,0.45)\) | \((0.85,0.55)\) | expose joint-1 transmission structure |
| T3 — joint-2 dominant | \((0.45,0.15)\) | \((0.55,0.85)\) | expose joint-2 transmission structure |

For axis \(i\), convert a normalized fraction \(z_i\) to

\[
q_i=q_{i,\min}+z_i(q_{i,\max}-q_{i,\min}).
\]

The same absolute \(\mathbf q_s,\mathbf q_g\) must be used for the four-bar and
gearbox inside a pair. A task failure is recorded; it must not be silently moved
or resampled.

## Shared-Q graph contract

For each pair and resolution, construct one output topology

\[
G_Q=(V_Q,E_Q)
\]

and attach two actuator embeddings:

\[
\mathbf u_{\mathrm{FB}}(\mathbf q)
=g_{\mathrm{FB}}^{-1}(\mathbf q),
\qquad
\mathbf u_{\mathrm{GB}}(\mathbf q)
=g_{\mathrm{GB}}^{-1}(\mathbf q).
\]

Required pair invariants:

- identical node IDs and \(\mathbf q\) coordinates;
- identical base adjacency;
- identical exact-query node IDs and connectivity;
- identical valid/reachable output topology;
- output-linear transition provenance for both mechanisms;
- finite and continuous inverse mappings across every accepted edge;
- forward round-trip residual below configured tolerance.

If one mechanism rejects an edge that the other accepts, fail the pair and emit
a diagnostic trace. Do not interpret unequal feasible graphs as a cost effect in
this sprint.

## Cost family

For each edge trace, calculate

\[
d_Q(e)=\int_e\lVert d\mathbf q\rVert_2,
\qquad
d_U^{(m)}(e)=\int_e\lVert d\mathbf u_m\rVert_2.
\]

Normalize with the shared pair scales

\[
s_Q
=
\lVert\mathbf q_{\max}-\mathbf q_{\min}\rVert_2,
\qquad
s_U
=
\lVert\mathbf u_{\max}-\mathbf u_{\min}\rVert_2.
\]

Use

\[
c_{\alpha}^{(m)}(e)
=
\alpha\frac{d_Q(e)}{s_Q}
+
(1-\alpha)\frac{d_U^{(m)}(e)}{s_U}.
\]

Required weights:

\[
\alpha\in\{1.0,0.75,0.5,0.25,0.0\}.
\]

Interpretation:

- \(\alpha=1\): pure-\(Q\) null control; paths and expansions should agree across
  the pair, subject only to deterministic tie behavior;
- \(\alpha=0.5\): primary balanced planning-control view;
- \(\alpha=0\): pure actuator-travel comparison;
- intermediate values show when path divergence first appears.

Every result stores the raw \(L_Q\), raw \(L_U\), normalized components, and total
objective separately.

## Work packages

### V2-801 — Integrate the two-view research narrative

Update the canonical paper draft and literature map with:

- the hidden unit-gearbox assumption in conventional \(Q\)-only models;
- the mechanism view: uniform \(U\) mapped into deformed \(Q\);
- the planning-control view: common uniform \(Q\) with mechanism-dependent
  inverse embedding and weights;
- the distinction between coordinate mapping and resampling;
- the dual metric mappings \(J_g^\mathsf T W_QJ_g\) and
  \(J_g^{-\mathsf T}W_UJ_g^{-1}\);
- the narrative walk-up from familiar joint coordinates to mechanism-aware
  planning.

### V2-802 — Audit the shared uniform-Q graph

Review the existing Version 2 graph and query-overlay implementation rather than
building a parallel graph stack.

Verify:

- one topology can be reused across paired mechanism embeddings;
- node and edge provenance remains output-linear;
- unique inverse states are attached for every node and trace sample;
- exact query overlays use the same output state and candidate connectivity;
- serialization preserves the pair relationship and graph invariant report.

Document every corrected defect with a regression test.

### V2-803 — Materialize span-matched gearbox embeddings from Q

Extend or verify the ADR-012 materialization path so each accepted four-bar branch
produces a paired affine gearbox with:

- per-axis span ratios;
- explicit \(q_{\min},u_{\min}\) references;
- inverse \(Q\rightarrow U\) mapping;
- matching \(U\)-span and \(Q\)-span assertions;
- serialized source branch and matching provenance;
- required `span_matched_gearbox` labels.

### V2-804 — Add the normalized Q/U objective

Implement the ADR-017 objective as a registered Version 2 cost.

Requirements:

- configurable \(\alpha\);
- pair-level \(s_Q,s_U\);
- trace-integrated \(d_Q,d_U\);
- explicit units and dimensionless normalization metadata;
- raw and normalized component serialization;
- zero heuristic fallback;
- optional blended A* heuristic after admissibility validation.

### V2-805 — Freeze five mechanism pairs and three task templates

Create versioned fixture/config data containing:

- five four-bar arm definitions;
- branch certificates;
- five derived gearbox controls;
- three normalized task templates;
- graph resolution;
- five \(\alpha\) values;
- deterministic seeds and stable pair/task IDs.

No fixture may be embedded only in dashboard code.

### V2-806 — Implement paired study orchestration

For every pair-task-weight tuple:

1. build or load one shared \(Q\) topology;
2. attach four-bar and gearbox actuator embeddings;
3. insert identical exact start/goal overlays;
4. assert graph invariants;
5. run Dijkstra for both mechanisms;
6. optionally run validated A*;
7. store paired results and failure status without resampling.

Required hierarchy:

```text
run
└── task_set (3)
    └── mechanism_pair (5)
        └── alpha (5)
            ├── fourbar
            └── span_matched_gearbox
```

### V2-807 — Add comparison and path-divergence metrics

Required per mechanism:

- valid and reachable nodes/edges;
- expanded, generated, reopened, and stale nodes;
- expansion fraction;
- optimal combined cost;
- raw and normalized cost components;
- path nodes and edges;
- \(L_U,L_Q,L_X\);
- runtime as a secondary metric;
- inverse and endpoint residuals.

Required paired metrics:

- expansion and cost deltas;
- output-path node and edge overlap;
- output-path divergence onset as \(\alpha\) changes;
- Cartesian detour and maximum paired-path separation;
- actuator-travel ratio;
- null-control equality at \(\alpha=1\).

### V2-808 — Generate the side-by-side HTML dashboard

Extend the existing regenerable Version 2 canvas. Do not create a notebook-only
or server-dependent viewer.

The dashboard must provide:

- three task-set sections or tabs;
- five mechanism-pair columns within each task;
- an \(\alpha\) selector or clearly separated weight panels;
- four-bar and span-matched gearbox results side by side;
- branch \(q(u)\) and \(dq/du\) plots;
- shared \(Q\)-graph with expanded nodes and selected paths;
- both selected paths mapped into \(U\);
- Cartesian end-effector paths;
- metric cards and paired deltas;
- graph-invariant and null-control status;
- mechanism, task, cost, config, code-revision, and run provenance.

The HTML must open locally from `results/<run_id>/index.html` with relative assets.

### V2-809 — Add invariant and regression tests

At minimum:

- affine inverse fixture recovers exact \(U\);
- span-matched gearbox shares branch spans;
- four-bar forward/inverse round trip;
- paired graphs share node coordinates and adjacency;
- paired exact overlays are identical in \(Q\);
- pure-\(Q\) edge costs are identical across a pair;
- pure-\(Q\) optimal paths/costs/expansions satisfy the null control;
- blended cost equals the sum of stored normalized components;
- \(\alpha=0\) matches normalized actuator travel;
- component costs are nonnegative and finite;
- blended heuristic is admissible where enabled;
- all earlier Version 1 and Version 2 regressions pass.

### V2-810 — Run, review, and summarize

Produce one immutable diagnostic run containing all 15 pair-task cases and the
full weight sweep. The report must distinguish:

- changes caused by the objective weight;
- changes caused by mechanism nonlinearity;
- task dependence within the same mechanism pair;
- search-effort changes versus path-quality changes;
- null results where paths do not diverge.

Do not expand to Monte Carlo or 3R until this dashboard has been reviewed.

## Configuration sketch

```yaml
architecture_version: 2
study:
  name: shared_q_paired_2r
  mechanism_pair_ids: [pair_01, pair_02, pair_03, pair_04, pair_05]
  task_template_ids: [cross_range, joint1_dominant, joint2_dominant]
  alphas: [1.0, 0.75, 0.5, 0.25, 0.0]
  reference_algorithm: dijkstra
  optional_algorithms: [astar]

graph:
  sampling_domain: output
  transition_parameterization: output_linear
  shape: [64, 64]
  exact_query_overlays: true

comparison:
  linear_control: span_matched_gearbox
  require_identical_q_topology: true
  reject_on_pair_invariant_failure: true

cost:
  type: q_u_blend
  normalization:
    q_scale: output_box_diagonal
    u_scale: paired_branch_box_diagonal
```

## Verification commands

```bash
pytest tests/graphs_v2 tests/experiments_v2 tests/objectives_v2
python scripts/run_v2_experiment.py --config configs/v2/shared_q_paired_smoke.yaml
python scripts/run_v2_experiment.py --config configs/v2/shared_q_paired_2r.yaml
python scripts/generate_v2_canvas.py --latest
pytest
ruff check .
ruff format --check .
mypy src
```

## Non-goals

- no full-cycle or noninjective four-bar planning;
- no lifted \((q,\sigma)\) graph;
- no 3R implementation;
- no obstacles or collision checking;
- no dynamics, energy, or torque-limit claims;
- no mechanism optimization;
- no large random mechanism population;
- no claim that fewer expansions alone imply a better robot.

## Sprint exit criteria

1. The canonical research documents contain the two-view narrative and mappings.
2. Five certified four-bar arms and five span-matched gearbox controls are frozen.
3. The same five pairs run against three exact task sets.
4. Paired graphs pass identical-\(Q\)-topology and inverse-mapping invariants.
5. The five-weight normalized \(Q/U\) objective runs reproducibly.
6. The \(\alpha=1\) null control passes for every pair-task case.
7. All component, search, path, and divergence metrics are serialized.
8. One local HTML dashboard displays all 15 cases side by side across weights.
9. The full test, lint, formatting, and type-check suite passes.
10. V2.7 remains held until the V2.8 evidence is reviewed.

## Cursor starter prompt

```text
Implement Sprint V2.8 only. Reuse the Version 2 uniform-Q graph, operating-branch,
query-overlay, objective-registry, run-package, and HTML-canvas architecture. Freeze
five certified 2R four-bar arms and derive one per-arm span-matched affine gearbox
control. Reuse the same five pairs across three exact normalized-Q task templates.
Add the ADR-017 normalized additive Q/U objective with alpha values 1.0, 0.75,
0.5, 0.25, and 0.0. Require identical Q nodes, adjacency, query connectivity, and
reachable topology inside every pair; reject and diagnose any mismatch. Run
Dijkstra as reference, validate any blended A* heuristic, serialize raw and
normalized cost components, and extend the V2 HTML canvas to show Q search, U
embeddings, Cartesian paths, expansions, path metrics, pair deltas, and provenance
for all 3 x 5 cases. Do not implement full-cycle state, obstacles, dynamics, 3R,
or mechanism optimization.
```
