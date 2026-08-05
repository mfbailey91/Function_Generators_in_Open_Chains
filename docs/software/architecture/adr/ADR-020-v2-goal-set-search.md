# ADR-020 — Version 2 goal-set search semantics

**Status:** Accepted
**Applies to:** Version 2 exact graph search; required by Experiment B
**Related:** ADR-005, ADR-018; [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](../../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md)

## Context

V2.10 and V2.11 production solvers accepted one goal node. Experiment B asks a
known start state to reach any graph node whose Cartesian output lies in a
frozen goal disk. The generic search stack must support that query without a
second Cartesian planner or task-space logic inside the search core.

## Decision

### One generalized exact-search core

`best_first_search` and `GraphSolver.solve` accept exactly one active goal
representation:

1. `goal`: one valid node id, retained as the backward-compatible case;
2. `goal_node_ids`: one non-empty collection of valid node ids;
3. `goal_test(node_id) -> bool`: a graph-generic predicate.

Experiment B builds the explicit `goal_node_ids` set before search. Cartesian
membership is computed at the experiment layer; the search core sees only node
ids or a predicate.

Ambiguous goal forms, empty explicit sets, and invalid explicit goal ids raise
`ValueError` before the queue is initialized.

### Termination and deterministic ties

A node is a goal only when it is removed from the priority queue at its valid
best-known cost under the existing ADR-005 stale-entry semantics. The selected
goal is therefore optimally settled.

Priority remains

```text
(f, node_id)
```

so equal-cost candidate goals resolve deterministically by the existing node-id
tie order. The selected goal is `SearchResult.path[-1]`; Experiment B records
that node, its \(q\), \(u\), Cartesian position, residual, and IK family.

Expansion counting is unchanged. The settled goal counts as an expansion, as in
the single-goal implementation.

### Dijkstra baseline

Dijkstra uses the zero heuristic and terminates on the first optimally settled
goal-set member. Small-graph tests compare it against an exhaustive oracle that
minimizes the single-source distance over all explicit goal nodes.

### Accepted A* heuristic for actuator travel

For Experiment B's actuator-travel objective,

\[
c(a,b)=\|\mathbf u_b-\mathbf u_a\|_2,
\]

accept the goal-set heuristic

\[
h(v)=\min_{g\in V_G}\|\mathbf u_v-\mathbf u_g\|_2.
\]

It is admissible because the straight-line actuator displacement to any goal is
a lower bound on every path to that goal. It is consistent because distance to
a set is 1-Lipschitz under the same Euclidean metric:

\[
h(a)\le c(a,b)+h(b).
\]

The registry name is:

```text
input_euclidean_goal_set
```

This proof applies only to `actuator_travel` / `input_euclidean` edge costs.
Raw Cartesian distance is not accepted as a heuristic for this objective.
Other cost families remain blocked until separately documented and tested.

### Empty and disconnected goal sets

- An empty explicit goal set is a task-construction failure and search refuses
  to start.
- A non-empty but disconnected goal set returns the existing `found=False`,
  empty path, and infinite cost result after exhausting the reachable component.
- Experiment B distinguishes those outcomes in its failure taxonomy.

## Compatibility

Single-goal callers continue to pass `goal` positionally and require no result
schema change. Query overlays and existing Dijkstra/A* campaigns remain valid.
No OMPL, sampling-based, Cartesian-native, or per-IK repeated-search stack is
introduced.

## Required tests

- backward-compatible single-goal result identity;
- explicit goal set selects the cheapest settled goal;
- deterministic equal-cost goal selection;
- explicit set and predicate equivalence on small graphs;
- ambiguous and empty goal specifications fail closed;
- goal-set Dijkstra matches an exhaustive oracle;
- goal-set A* and Dijkstra return equal optimal cost;
- accepted heuristic is zero on every goal, admissible against exact distances,
  and consistent on every tested edge.

## Consequences

- V2.12 may implement Dijkstra and A* goal-region smoke together.
- A* results must name `input_euclidean_goal_set` explicitly.
- Production remains blocked on Cartesian calibration and crossed-statistics
  decisions, not on goal-set search semantics.
