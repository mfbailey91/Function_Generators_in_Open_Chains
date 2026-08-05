# Sprint V2.9 — Shared-Q Paired Mechanism Study

## Theme

> Hold the possible arm motions fixed, then observe how different transmissions value and traverse them using actuator distance alone.

## Scope revision

This sprint replaces the proposed normalized \(Q/U\) blend and weight sweep with one planning objective:

\[
c_U^{(m)}(a,b)
=
\left\|
\mathbf u_m(\mathbf q_b)-\mathbf u_m(\mathbf q_a)
\right\|_2.
\]

Everything else in the shared-\(Q\) paired study remains fixed:

- five certified monotonic 2R four-bar arms;
- one span-matched affine gearbox control for each arm;
- three deterministic exact start-goal task sets;
- one common uniform-\(\mathcal Q\) topology within each mechanism pair;
- identical graph resolution, transition provenance, task overlays, algorithms,
  metrics, result packaging, and HTML dashboard structure;
- Sprint V2.7 remains held.

The sprint must not add a \(Q\)-distance term, an \(alpha\) parameter, a cost-weight
sweep, or a new multiobjective cost.

## Objective

Turn the Version 2 shared-output architecture into a focused, inspectable study of
five monotonic four-bar arms and five span-matched gearbox controls. Evaluate the
same five mechanism pairs across three deterministic start-goal task sets using
actuator-space distance as the only planning cost, and generate one HTML dashboard
that shows the resulting paths and search behavior in \(\mathcal U\), \(\mathcal Q\),
and \(\mathcal X\).

## Sprint question

> When a four-bar arm and a span-matched gearbox arm share exactly the same output-state graph, how does minimizing actuator travel alone change search effort and the selected output and Cartesian paths across different tasks?

## Narrative role

This sprint implements the **planning-control view** that follows the paper's
**mechanism view**:

1. Uniform \(\mathcal U\) mapped into \(\mathcal Q\) explains what the function
   generator physically generates.
2. Uniform \(\mathcal Q\) mapped into mechanism-specific \(\mathcal U\) provides
   the apples-to-apples planning comparison.

A uniform output graph initially obscures the mechanism because all arms appear
to have the same nodes. The mechanism re-enters through the unique inverse map

\[
\mathbf u_m=g_m^{-1}(\mathbf q)
\]

and through the actuator distance assigned to each otherwise identical output
transition. The study therefore isolates one claim:

> The mechanism does not change which arm configurations are offered to the planner; it changes the actuator-space meaning of moving between them.

## Accepted scope decisions

- Use **certified monotonic branches only**.
- Freeze **five 2R four-bar arms**. Each arm contains one accepted monotonic
  four-bar branch per joint.
- Pair each arm with its own **span-matched affine gearbox arm** under ADR-012.
- Reuse those same five mechanism pairs across **three task sets** with different
  exact start and goal states.
- Use one common uniform-\(\mathcal Q\) graph within each mechanism pair.
- Use the existing Version 2 `actuator_travel` objective only.
- Use raw actuator distance for planning. Store normalized actuator distance only
  as a reporting metric when cross-pair comparison requires it.
- Retain Dijkstra as the reference algorithm.
- Retain A* only with the existing compatible input-Euclidean heuristic and require
  exact optimal-cost agreement with Dijkstra.
- Keep Sprint V2.7 3R work held.

## Experiment cardinality

The fixed diagnostic study contains:

- 5 mechanism pairs;
- 3 task sets;
- 1 cost objective;
- 2 mechanisms per pair.

This produces 15 pair-task cases and 30 reference Dijkstra runs:

\[
5\times3\times1\times2=30.
\]

If A* is retained, it adds 30 runs using the same graphs, tasks, and actuator cost.
No weight sweep is permitted.

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
inside each pair's shared output box.

| Task | Start fraction | Goal fraction | Purpose |
| --- | --- | --- | --- |
| T1 — cross-range | \((0.15,0.20)\) | \((0.85,0.80)\) | long diagonal movement through both axes |
| T2 — joint-1 dominant | \((0.15,0.45)\) | \((0.85,0.55)\) | expose joint-1 transmission structure |
| T3 — joint-2 dominant | \((0.45,0.15)\) | \((0.55,0.85)\) | expose joint-2 transmission structure |

For axis \(i\), convert normalized fraction \(z_i\) to

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
- identical valid and reachable output topology;
- output-linear transition provenance for both mechanisms;
- finite and continuous inverse mappings across every accepted edge;
- forward round-trip residual below the configured tolerance.

If one mechanism rejects an edge that the other accepts, fail the pair and emit a
diagnostic trace. Do not interpret unequal feasible graphs as a cost effect in
this sprint.

## Planning objective

For mechanism \(m\), assign each graph edge

\[
c_U^{(m)}(a,b)
=
\left\|
\mathbf u_m(\mathbf q_b)-\mathbf u_m(\mathbf q_a)
\right\|_2.
\]

The path objective is

\[
C_U^{(m)}(P)
=
\sum_{(a,b)\in P}c_U^{(m)}(a,b).
\]

Use the existing Version 2 registry name:

```yaml
objective:
  cost: actuator_travel
  heuristic: input_euclidean
```

For Dijkstra, the heuristic is ignored. For A*, the straight-line input-space
heuristic is

\[
h_U^{(m)}(n)
=
\left\|
\mathbf u_m(\mathbf q_n)-\mathbf u_m(\mathbf q_g)
\right\|_2.
\]

The A* implementation must return the same optimal cost as Dijkstra for every
accepted trial.

### Reporting normalization

The planner uses raw actuator distance. For summaries across pairs, additionally
report

\[
\widehat L_U
=
\frac{L_U}
{\left\|\mathbf u_{\max}-\mathbf u_{\min}\right\|_2}.
\]

This normalization is descriptive only. It must not alter edge weights, paths,
queue ordering, or expansion counts.

### Required path measurements

Even though only \(U\)-distance determines the selected path, every result must
still report:

- \(L_U\): actuator path length;
- \(L_Q\): output-joint path length;
- \(L_X\): Cartesian end-effector path length;
- output-path node and edge sequence;
- mapped actuator path;
- Cartesian path.

The non-objective measurements show the consequences of minimizing actuator
travel without adding them back into the planner.

## Work packages

### V2-801 — Integrate the two-view research narrative

Update the canonical paper draft and literature map with:

- the hidden unit-gearbox assumption in conventional \(Q\)-only models;
- the mechanism view: uniform \(U\) mapped into deformed \(Q\);
- the planning-control view: common uniform \(Q\) with mechanism-dependent
  inverse embedding and actuator distance;
- the distinction between coordinate mapping and resampling;
- the dual metric mappings \(J_g^\mathsf T W_QJ_g\) and
  \(J_g^{-\mathsf T}W_UJ_g^{-1}\);
- the narrative walk-up from familiar joint coordinates to mechanism-aware
  planning.

Do not introduce a hybrid \(Q/U\) planning objective into the research narrative
for this sprint.

### V2-802 — Audit the shared uniform-Q graph

Review the existing Version 2 graph and query-overlay implementation rather than
building a parallel graph stack.

Verify:

- one topology can be reused across paired mechanism embeddings;
- node and edge provenance remains output-linear;
- unique inverse states are attached for every node;
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

### V2-804 — Freeze the actuator-travel objective

Use the existing registered `actuator_travel` cost. Do not implement a new cost
family.

Verify:

- edge cost equals endpoint Euclidean distance in attached actuator state;
- four-bar and gearbox costs are evaluated on the same ordered \(Q\)-edge;
- costs are finite, nonnegative, and symmetric;
- the input-Euclidean A* heuristic is compatible;
- Dijkstra and A* return equal optimal costs;
- raw edge and path \(U\)-distance remain available in result serialization;
- no \(Q\)-distance contribution, \(alpha\), or hidden normalization affects the
  planner.

### V2-805 — Freeze five mechanism pairs and three task templates

Create versioned fixture and config data containing:

- five four-bar arm definitions;
- branch certificates;
- five derived gearbox controls;
- three normalized task templates;
- graph resolution;
- deterministic seeds and stable pair and task IDs;
- one fixed objective: `actuator_travel`.

No fixture may be embedded only in dashboard code.

### V2-806 — Implement paired study orchestration

For every pair-task tuple:

1. build or load one shared \(Q\) topology;
2. attach four-bar and gearbox actuator embeddings;
3. insert identical exact start and goal overlays;
4. assert graph invariants;
5. resolve `actuator_travel` for each mechanism;
6. run Dijkstra for both mechanisms;
7. run A* only with `input_euclidean` if enabled;
8. store paired results and failure status without resampling.

Required hierarchy:

```text
run
└── task_set (3)
    └── mechanism_pair (5)
        ├── fourbar
        └── span_matched_gearbox
```

### V2-807 — Add comparison and path-divergence metrics

Required per mechanism:

- valid and reachable nodes and edges;
- expanded, generated, reopened, and stale nodes;
- expansion fraction;
- optimal actuator-travel cost;
- raw and normalized \(L_U\);
- path nodes and edges;
- \(L_U,L_Q,L_X\);
- runtime as a secondary metric;
- inverse and endpoint residuals.

Required paired metrics:

- expansion and actuator-cost deltas;
- output-path node and edge overlap;
- whether the selected \(Q\)-paths differ;
- Cartesian detour and maximum paired-path separation;
- actuator-travel ratio;
- Dijkstra/A* optimal-cost agreement.

There is no path-divergence onset metric because there is no cost-weight sweep.

### V2-808 — Generate the side-by-side HTML dashboard

Extend the existing regenerable Version 2 canvas. Do not create a notebook-only
or server-dependent viewer.

The dashboard must provide:

- three task-set sections or tabs;
- five mechanism-pair columns within each task;
- four-bar and span-matched gearbox results side by side;
- one clearly labeled objective: actuator travel only;
- branch \(q(u)\) and \(dq/du\) plots;
- shared \(Q\)-graph with expanded nodes and selected paths;
- both selected paths mapped into \(U\);
- Cartesian end-effector paths;
- metric cards and paired deltas;
- graph-invariant status;
- mechanism, task, cost, config, code-revision, and run provenance.

The dashboard must not contain an \(alpha\) selector or blended-cost panel. The
HTML must open locally from `results/<run_id>/index.html` with relative assets.

### V2-809 — Add invariant and regression tests

At minimum:

- affine inverse fixture recovers exact \(U\);
- span-matched gearbox shares branch spans;
- four-bar forward/inverse round trip;
- paired graphs share node coordinates and adjacency;
- paired exact overlays are identical in \(Q\);
- `actuator_travel` equals endpoint Euclidean \(U\)-distance;
- input-Euclidean heuristic does not overestimate exact reverse-Dijkstra cost on
  representative fixtures;
- Dijkstra and A* return equal optimal cost;
- raw and normalized \(U\)-metrics are nonnegative and finite;
- no \(Q\)-term or blend parameter is present in the sprint config;
- all earlier Version 1 and Version 2 regressions pass.

The existing pure-\(Q\) null-control tests remain regression tests for the
architecture, but they are not an additional experiment in this sprint.

### V2-810 — Run, review, and summarize

Produce one immutable diagnostic run containing all 15 pair-task cases. The
report must distinguish:

- changes caused by mechanism nonlinearity;
- task dependence within the same mechanism pair;
- search-effort changes versus output and Cartesian path-quality changes;
- cases where the mechanisms choose the same output path despite different
  actuator costs;
- cases where actuator-only optimization produces longer \(Q\) or \(X\) paths.

Do not expand to Monte Carlo, a cost blend, or 3R until this dashboard has been
reviewed.

## Configuration sketch

```yaml
architecture_version: 2
planning_space: output
seed: 12345

study:
  name: shared_q_paired_2r_u_distance_only
  mechanism_pair_ids: [pair_01, pair_02, pair_03, pair_04, pair_05]
  task_template_ids: [cross_range, joint1_dominant, joint2_dominant]

sampling:
  domain: output
  shape: [64, 64]

transitions:
  parameterization: output_linear

exact_query_overlays: true

comparison:
  linear_control: span_matched_gearbox
  require_identical_q_topology: true
  reject_on_pair_invariant_failure: true

objective:
  cost: actuator_travel
  heuristic: input_euclidean

algorithms: [dijkstra, astar]
```

The final field names must follow the existing strict Version 2 schema. The
configuration sketch defines intent; it does not authorize parallel config
parsing or schema aliases.

## Verification commands

```bash
pytest tests/graphs_v2 tests/experiments_v2 tests/objectives_v2
python scripts/run_v2_experiment.py --config configs/v2/shared_q_paired_u_smoke.yaml
python scripts/run_v2_experiment.py --config configs/v2/shared_q_paired_u_2r.yaml
python scripts/generate_v2_canvas.py --latest
pytest
ruff check .
ruff format --check .
mypy src
```

## Non-goals

- no \(Q/U\) blend or \(alpha\) sweep;
- no \(Q\)-distance regularization in the planning objective;
- no new cost implementation when `actuator_travel` already satisfies the
  contract;
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
5. Every planning run uses `actuator_travel` as its only edge objective.
6. No \(Q\)-weight, \(alpha\), or objective sweep appears in the sprint configs or
   dashboard.
7. Dijkstra and A* agree on optimal actuator-travel cost wherever A* is enabled.
8. All search, \(U/Q/X\) path, comparison, and provenance metrics are serialized.
9. One local HTML dashboard displays all 15 cases side by side.
10. The full test, lint, formatting, and type-check suite passes.
11. V2.7 remains held until the V2.9 evidence is reviewed.

## Cursor starter prompt

```text
Implement the revised Sprint V2.9 only. Reuse the Version 2 uniform-Q graph,
operating-branch, exact-query-overlay, objective-registry, run-package, and HTML
canvas architecture. Freeze five certified 2R four-bar arms and derive one
per-arm span-matched affine gearbox control. Reuse the same five pairs across
three exact normalized-Q task templates. Use the existing `actuator_travel`
objective exclusively, with edge cost equal to Euclidean distance between the
attached actuator states of adjacent Q nodes. Do not add Q distance, a Q/U blend,
alpha values, normalization inside the planner, or a cost sweep. Require
identical Q nodes, adjacency, query connectivity, and reachable topology inside
every pair; reject and diagnose any mismatch. Run Dijkstra as the reference and
A* only with the compatible input-Euclidean heuristic, requiring equal optimal
cost. Serialize L_U, normalized L_U for reporting, L_Q, L_X, expansions, path
overlap, pair deltas, residuals, and provenance. Extend the V2 HTML canvas to
show Q search, U embeddings, Cartesian paths, and metric cards for all 3 x 5
cases. Do not implement full-cycle state, obstacles, dynamics, 3R, mechanism
optimization, or any additional planning objective.
```
