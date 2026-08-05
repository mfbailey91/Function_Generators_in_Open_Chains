# Experiment B — 2R Cartesian position goal-region planning

**Status:** accepted conceptual design; not active implementation  
**Robot:** planar 2R  
**Task variable:** Cartesian position \((x,y)\), not full pose  
**Primary graph:** shared uniform-\(\mathcal Q\) Version 2 graph  
**Primary objective:** actuator travel  
**Initial solver:** Dijkstra goal-set search  
**Planned sprint:** [`SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md`](../../planning/sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md) (held)  
**Prerequisites:** [ADR-019](../../architecture/adr/ADR-019-v2-cartesian-task-domain.md) (proposed), [ADR-020](../../architecture/adr/ADR-020-v2-goal-set-search.md) (proposed), [crossed-statistics note](../../architecture/notes/PROJECT_NOTE_EXPERIMENT_B_CROSSED_STATISTICS.md)

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

Task-bank generation must:

1. sample \(\mathbf x_s\);
2. enumerate certified discrete \(\mathcal Q\)-states that reach its tolerance
   region;
3. choose one according to a frozen balancing policy;
4. store the resulting \(\mathbf q_s\) and graph node;
5. use that identical start node for the four-bar and matched gearbox.

The bank must record:

- all analytic IK families;
- which lie inside the certified shared \(\mathcal Q\)-box;
- which have discrete graph representatives;
- which were excluded and why;
- the selected start family.

That prevents “balanced IK” from being mistaken for balance over unrestricted
planar 2R kinematics. Selection must not depend on mechanism cost or search
outcomes.

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

### A* follow-on

A* is blocked until an admissible heuristic to the goal set is documented and
validated:

\[
h(v)
\le
\min_{g\in V_G}
d(v,g).
\]

ADR-018's single-goal `input_euclidean` heuristic is not automatically valid
for a goal set. Raw Cartesian distance is not automatically admissible under
actuator-travel edge cost. Zero heuristic remains a valid fallback and is
equivalent to Dijkstra.

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

1. ADR-019 has accepted the external Cartesian domain and task-bank schema;
2. Cartesian-uniform sampling is validated;
3. start IK selection is frozen, recorded, and mechanism-independent;
4. ADR-020 has accepted goal-set search semantics;
5. goal-set Dijkstra matches an exhaustive small-graph oracle;
6. pair goal-set invariants pass;
7. goal-radius and resolution sensitivity stabilize;
8. unreachable tasks are preserved as outcomes;
9. crossed task/mechanism uncertainty is implemented;
10. one versioned command reproduces the smoke and production packages;
11. the report names the task distribution, solver, and conditional estimand
    explicitly.
