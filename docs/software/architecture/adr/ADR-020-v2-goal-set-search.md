# ADR-020 — Version 2 goal-set search semantics

**Status:** Proposed prerequisite; not accepted  
**Applies to:** Version 2 exact graph search; required by Experiment B  
**Related:** ADR-005, ADR-018; [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](../../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md)

## Context

Current production solvers expose a single goal node:

```python
solve(graph, start, goal, objective, *, record_expanded=False)
```

Experiment B needs termination on any node whose Cartesian output lies in a
frozen goal disk. The generic search layer should gain that capability without
introducing a separate Cartesian planner stack or leaking task-space geometry
into the search core.

This ADR is a placeholder. It records the intended API shape and the decisions
that must be frozen before Sprint V2.12 implementation.

## Intended decision

Generalize the existing solver contract rather than bypass it. A candidate
shape is:

```python
solve(
    graph,
    start_node_id,
    goal_node_ids=None,
    goal_test=None,
    objective,
    *,
    record_expanded=False,
)
```

Exactly one goal representation may be active:

- a single-goal node, as today's backward-compatible special case;
- an explicit `goal_node_ids` collection; or
- a `goal_test(node_id) -> bool` predicate.

For Experiment B, `goal_test` would test whether the node's Cartesian output
lies inside the frozen goal disk. Cartesian membership is computed outside or
in the predicate closure; the search core remains graph-generic.

## Decisions required before acceptance

- termination when a goal node is optimally settled;
- deterministic behavior if several goal nodes have equal cost;
- empty-goal-set and disconnected-goal-set status codes;
- goal-set instrumentation (`selected_goal_node_id`, settled-goal cost,
  goal-set size or digest);
- reporting of selected \(\mathbf q_g\), \(\mathbf u_g\), Cartesian residual,
  and IK family at the experiment layer;
- Dijkstra oracle equivalence on small graphs;
- A* admissibility requirements for a goal set, including that ADR-018's
  single-goal `input_euclidean` heuristic is not automatically valid;
- compatibility with exact start query overlays from V2.6;
- expansion-count semantics unchanged from ADR-005 except for multi-goal
  termination.

## Consequences once accepted

- Dijkstra remains the Experiment B baseline.
- A* on Experiment B stays blocked until a documented admissible goal-set
  heuristic is accepted.
- Production GraphSolver implementations share one API.
- No OMPL, sampling-based, or Cartesian-native planner is introduced for this
  experiment.

## Status note

Do not change `graph_solver.py` or `best_first_search` against this
placeholder.
