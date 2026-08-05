# Experiment B — 2R Cartesian position goal-region planning

**Status:** active bounded implementation in Sprint V2.12; production not authorized
**Robot:** planar 2R
**Task variable:** Cartesian position \((x,y)\), not full pose
**Primary graph:** shared uniform-\(\mathcal Q\) Version 2 graph
**Primary objective:** actuator travel
**Initial solvers:** Dijkstra baseline and A* with `input_euclidean_goal_set` under the `smoke_oracle_pair_v1` correctness policy
**Active sprint:** [`SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md`](../../planning/sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md)
**Accepted implementation contracts:** [ADR-019](../../architecture/adr/ADR-019-v2-cartesian-task-domain.md), [ADR-020](../../architecture/adr/ADR-020-v2-goal-set-search.md). **Production prerequisite:** [crossed-statistics note](../../architecture/notes/PROJECT_NOTE_EXPERIMENT_B_CROSSED_STATISTICS.md) must be converted into an implemented decision before population inference.

## Research question

> Starting from a known physical robot state, how does a nonlinear transmission
> change reachability, selected final posture, path cost, and graph-search effort
> when the robot is asked to reach a Cartesian position region rather than one
> preselected joint configuration?

Experiment B is the representative 2R planning case. A two-degree-of-freedom
planar arm can independently specify Cartesian position \((x,y)\), but it cannot
independently specify end-effector orientation.

## Query semantics

The scientific query is:

\[
\text{known physical start state}
\longrightarrow
\text{Cartesian position goal region}.
\]

Any certified output configuration satisfying

\[
\lVert f(\mathbf q)-\mathbf x_g\rVert_2
\le
\epsilon_X
\]

is an accepted goal.

Each frozen task contains:

- a sampled Cartesian start position \(\mathbf x_s\);
- one frozen valid start configuration \(\mathbf q_s\) and its graph node;
- the corresponding known actuator state for each mechanism;
- a sampled Cartesian goal center \(\mathbf x_g\);
- a Cartesian goal tolerance \(\epsilon_X\).

The goal region is

\[
\mathcal R_X(\mathbf x_g,\epsilon_X)
=
\left\{
\mathbf x\in\mathbb R^2:
\lVert\mathbf x-\mathbf x_g\rVert_2\le\epsilon_X
\right\}.
\]

For graph \(G=(V,E)\), the goal-node set is

\[
V_G
=
\left\{
v\in V:
f(\mathbf q_v)\in\mathcal R_X
\right\}.
\]

The search begins at one known start node and terminates when the cheapest goal
node is settled. No particular elbow posture, joint endpoint, or actuator
endpoint is chosen in advance as the goal.

## Why the start is frozen but the goal is a set

A robot begins a planning query in a known physical state. The task generator
may sample the start Cartesian position, but it must resolve that position once
to a concrete start configuration before either mechanism is searched.

The goal is different: the external task asks the end effector to reach a
position region. Any valid final posture satisfying that region is acceptable.

This prevents the experiment from manufacturing an arbitrary goal posture that
the task itself did not require.

## Start semantics

Although tasks are sampled as Cartesian start and goal positions, the actual
planning query begins at one known physical state.

For the bounded V2.12 smoke, task attachment must:

1. sample \(\mathbf x_s\);
2. enumerate valid shared-graph nodes inside `start_tolerance`;
3. select the node with minimum Cartesian residual, breaking ties by node id;
4. store the resulting \(\mathbf q_s\), node id, residual, IK-family label, and
   attachment-policy id;
5. use that identical start node for the four-bar and matched gearbox.

The smoke policy is
`nearest_valid_graph_node_within_tolerance_v1`. Analytic IK families are
diagnostics: they record certified-box membership, nearest discrete
representatives, and exclusions. They do not choose or balance the smoke start.

The bank must record:

- all analytic IK families;
- which lie inside the certified shared \(\mathcal Q\)-box;
- which have discrete graph representatives;
- which were excluded and why;
- the selected start family.

Production must either retain this discrete attachment after calibration or
freeze a separate IK-family balancing / start-only exact-overlay policy. It must
not describe the current smoke as balanced IK. Selection may never depend on
mechanism cost or search outcomes.

## Primary task distribution: fixed external Cartesian domain

The primary distribution is a fixed external Cartesian domain \(\mathcal D_X\)
shared across the mechanism population. Pair-local reachable-workspace sampling
is a control, not the main experiment.

Do **not** define the primary domain as the intersection of all sampled
mechanism workspaces. That would let the mechanism population shrink and shape
the external exam.

The cleaner primary contract, to be frozen in ADR-019, is:

1. define a fixed external Cartesian region from the nominal 2R arm geometry
   and intended application area;
2. freeze one area-uniform task bank independently of the mechanism population;
3. treat reachability as an experimental outcome;
4. report planning metrics conditionally on valid start and goal construction;
5. use pair-local workspace sampling only as a secondary planning-only control.

Experiment B therefore measures both

\[
P(\text{task admissible/reachable})
\]

and

\[
\mathbb E[\text{search metric}\mid\text{task admissible/reachable}].
\]

Within one four-bar / matched-gearbox pair, the shared \(\mathcal Q\) graph and
shared forward kinematics require identical Cartesian node positions and
identical goal sets. A reachability mismatch inside a pair is an implementation
defect.

Search metrics must not silently discard unreachable tasks without reporting
coverage.

## Secondary control: pair-local reachable-workspace sampling

An optional control may sample uniformly from each mechanism pair's own
reachable Cartesian workspace.

This answers:

> Conditional on using the workspace supplied by this pair, how does the
> transmission change planning?

It does not give every mechanism the same external exam and must not replace the
fixed-domain primary analysis. It requires a separate experiment identifier.

## Uniform Cartesian sampling

Uniformity applies to Cartesian area, not to graph nodes and not to joint
coordinates.

The task generator must not approximate Cartesian-uniform sampling by drawing
uniform \(\mathbf q\) and mapping through forward kinematics. That induces a
Jacobian-weighted Cartesian distribution.

Acceptable generation methods include:

- direct area-uniform sampling from an analytic domain followed by IK
  feasibility checks;
- rejection sampling from a documented bounding region;
- area-weighted sampling from a precomputed Cartesian occupancy
  representation, with convergence checks.

The generator must record acceptance rates and all rejection reasons.

## Goal-region calibration

The Cartesian radius \(\epsilon_X\) must be calibrated before production.

It should be large enough that the accepted production graph usually contains
at least one goal node for reachable centers, but small enough that the query
still represents local Cartesian accuracy rather than a broad workspace sector.

The domain contract must also define the relationship between minimum
start–goal Cartesian separation and \(\epsilon_X\), including whether the start
pose may lie inside the goal disk.

Calibration must report:

- goal-set cardinality distribution;
- distance from requested goal center to the nearest graph node;
- empty-goal-set rate by graph resolution;
- selected-goal residual;
- sensitivity of expansion effects to candidate radii.

The accepted radius is frozen before production search.

## Search algorithm

No separate Cartesian planner stack is introduced. The existing single-goal
search API is generalized by ADR-020.

### Dijkstra baseline

Dijkstra requires no new heuristic assumption. The search terminates when a
valid best-known goal node is removed from the queue.

The implementation must support a goal predicate or explicit goal-node set. It
must not run one separate search per IK goal.

For Experiment B, a natural predicate is:

```python
goal_test(node_id) -> bool
```

testing whether the node's Cartesian output lies inside the frozen goal disk.

### A* actuator-travel heuristic

ADR-020 accepts the explicit goal-set lower bound

\[
h(v)=\min_{g\in V_G}\lVert \mathbf u_v-\mathbf u_g\rVert_2.
\]

For actuator-travel edge cost this is admissible and consistent by the triangle
inequality. The stable registry name is `input_euclidean_goal_set`. Raw
Cartesian distance remains unapproved for this objective. Dijkstra and A* must
return equal optimal cost for every accepted smoke query; a disagreement is a
hard implementation failure.

## Paired invariants

For each mechanism pair and Cartesian task:

1. the start \(\mathbf q_s\) and start node are identical;
2. the Cartesian coordinate attached to every shared graph node is identical;
3. the goal-node set \(V_G\) is identical;
4. the start-node and goal-set reachability status is identical;
5. deterministic search semantics are identical;
6. only the mechanism-specific actuator realization, edge cost, and resulting
   search order may differ.

## Result schema additions

Each trial must record at minimum:

```text
experiment_id
task_distribution_id
cartesian_domain_id
task_id
requested_start_x
analytic_start_ik_families
in_box_start_ik_families
discrete_start_graph_representatives
excluded_start_families_and_reasons
selected_start_ik_family
selected_start_q
selected_start_node_id
realized_start_x
requested_goal_x
goal_radius_x
goal_set_node_ids_or_digest
goal_set_size
nearest_goal_node_residual_x
selected_goal_node_id
selected_goal_q
selected_goal_u
selected_goal_x
selected_goal_residual_x
selected_goal_ik_family
start_feasible
goal_region_reachable
paired_query_valid
failure_or_exclusion_reason
```

Existing search, path-length, mechanism, graph, and provenance fields remain
required.

## Statistical design

The external Cartesian task bank is shared across mechanism pairs. Tasks and
mechanisms therefore form a crossed design:

\[
\Delta_{mk}
=
\mu+\alpha_m+\beta_k+\varepsilon_{mk}.
\]

This is not the Experiment A nested-task design. Sequential precision and
bootstrap logic from V2.10/V2.11 must not be copied unchanged.

See the prerequisite note
[`PROJECT_NOTE_EXPERIMENT_B_CROSSED_STATISTICS.md`](../../architecture/notes/PROJECT_NOTE_EXPERIMENT_B_CROSSED_STATISTICS.md).

Primary reports:

1. external task coverage and paired solve rate;
2. conditional paired log expansion ratio;
3. actuator path-length difference;
4. selected final posture and IK-family frequency;
5. task-location, separation, and direction diagnostics;
6. sensitivity to goal radius and graph resolution.

## Task descriptors

Compute pre-search descriptors from the frozen task bank:

- start radius and polar angle;
- goal radius and polar angle;
- Cartesian separation;
- chord direction;
- distance to analytic robot-workspace boundaries;
- number of analytic, in-box, and discrete start IK solutions;
- goal-set cardinality after graph construction.

These are explanatory descriptors. Do not create post-hoc task categories and
then present them as preregistered primary hypotheses.

## Relationship to Experiment A

Experiment A remains the controlled \(\mathcal Q\)-space metric probe.
Experiment B asks how the same graph machinery is used for a robot task.

The Experiment A `medium_diagonal` observation already failed its first
persistence check under A*. It may motivate exploratory diagnostics later, but
it does not alter Experiment B's uniform external task distribution and must
not tune \(\mathcal D_X\).

## Exit criteria

Experiment B is scientifically runnable only when:

1. ADR-019 remains the accepted external Cartesian domain and task-bank schema;
2. Cartesian-uniform sampling is validated;
3. start IK selection is frozen, recorded, and mechanism-independent;
4. ADR-020 remains the accepted goal-set Dijkstra/A* semantics;
5. goal-set Dijkstra matches an exhaustive small-graph oracle;
6. pair goal-set invariants pass;
7. goal-radius and resolution sensitivity stabilize;
8. unreachable tasks are preserved as outcomes;
9. crossed task/mechanism uncertainty is implemented;
10. one versioned command reproduces the smoke and production packages;
11. the report names the task distribution, solver, and conditional estimand
    explicitly.
