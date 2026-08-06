# Sprint V3.3 — Lattice and Local-Motion Validation

**Status:** active — eight-connected lattice, exact-start overlay, integrated edge cost  
**Code authorization:** V3-300–V3-305 only  
**Depends on:** [Sprint V3.2](SPRINT_V3_2_DIRECT_2R_VERTICAL_SLICE.md) (completed); ADRs 021–026  
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M3 (narrowed)

## Sprint intent

Validate Version 3 lattice search against continuous local-motion and integrated actuator cost: eight-connected simultaneous-joint topology for planar 2R, exact-start query overlay (ADR-023), Dijkstra/A* through `GraphSearchPlanner`, and 4-connected / endpoint-cost ablations—without sampling-based planners, obstacles, or Monte Carlo.

## Entry conditions

1. V3.2 direct planners, Cartesian disk goals, connectors, and classification are accepted and green.
2. ACTIVE_SPRINT explicitly activates V3.3.
3. Default V2 lattice topology remains four-connected (axis-aligned) for frozen evidence parity.

## Non-goals

- weighted A*, bidirectional search, any-angle / shortcut search;
- richer-than-eight connectivity;
- Cartesian disk / goal-set search on the lattice (`ExactOutputGoal` + overlay only);
- `planners/lattice/` package rename;
- PRM/RRT/OMPL (V3.4–V3.5);
- obstacle scenes (V3.7);
- population Monte Carlo / production inference;
- reinterpreting frozen Experiment A or Experiment B packages.

## Work packages

### V3-300 — Sprint contract and activation

Author this contract; close V3.2; authorize V3-300–V3-305 only.

### V3-301 — Configurable lattice connectivity

Extend `TensorGridTopology` with planner-configuration connectivity (`axis_aligned` vs `chebyshev_1` / eight-connected in 2D). Preserve the axis-aligned default for V2.

### V3-302 — Integrated lattice edge cost

Bridge lattice edges through V3.2 `OutputLinearMotion` / `InputLinearMotion` and `ActuatorTravelObjective.motion_cost`. Support declared `integrated` and `endpoint` cost modes. Validate motions with `FreeSpaceScene` when available.

### V3-303 — Exact-start query overlay

Extend `GraphSearchPlanner` to attach off-lattice exact `PhysicalState` start/goal via `QueryOverlayGraph`. No task-semantic `start_tolerance`. Record attachment diagnostics under `planner_metrics["graph"]` only.

### V3-304 — Lattice smoke and ablations

Deterministic paired four-bar / span-matched gearbox smoke: eight-connected + integrated cost with Dijkstra and A*; ablation rows for four-connected and endpoint cost.

### V3-305 — Tests

Topology neighbor sets, integrated vs endpoint cost properties, overlay exact-start, Dijkstra↔A* cost parity, and V2 compatibility fixture regression.

## Exit criteria

1. Eight-connected lattice search runs through V3 `PlanningProblem` / `GraphSearchPlanner` with integrated actuator edge cost.
2. Exact off-lattice starts attach via overlay without introducing start-tolerance task semantics.
3. Dijkstra and A* agree on path cost for the same graph and objective (within documented tolerance).
4. Four-connected and endpoint-cost ablations are runnable and tested.
5. Default four-connected + endpoint `actuator_travel` V2/V3 compatibility fixture remains green.
6. No PRM/RRT/OMPL/obstacle/Monte Carlo work activated opportunistically.
7. Hand off to V3.4 for native roadmap and tree planners.
