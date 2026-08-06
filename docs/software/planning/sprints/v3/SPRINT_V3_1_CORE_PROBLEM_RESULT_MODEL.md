# Sprint V3.1 — Core Planning Problem and Result Model

**Status:** drafted / not activated  
**Code authorization:** none until this sprint is explicitly activated after V3.0 contract acceptance  
**Depends on:** [Sprint V3.0](SPRINT_V3_0_ARCHITECTURE_CONTRACT.md); proposed ADRs 021–026  
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M1; [V3_MIGRATION_MAP.md](../../../architecture/notes/V3_MIGRATION_MAP.md)

## Sprint intent

Implement only the Version 3 core problem/result model and compatibility adapters around existing mechanism and search modules. Do not build new planner families, obstacles, OMPL, MoveIt, or Monte Carlo campaigns.

## Entry conditions

1. V3.0 freeze, inventory, ADRs 021–026, and migration map are accepted.
2. ACTIVE_SPRINT explicitly activates V3.1.
3. Version 2 golden and trusted regression suites remain green.

## Non-goals

- lattice eight-connected search;
- Cartesian production inference;
- native roadmap/tree planners;
- OMPL or ROS dependencies;
- source-tree reorganization beyond adding new modules beside stable packages;
- deleting legacy-only Version 1/V2 modules.

## Work packages

### V3-100 — Core interfaces

Implement modules for `PhysicalState`, `RobotModel`, `PlanningScene`, `GoalConstraint`, `ConstraintSet`, `LocalMotionModel`, `PlanningObjective`, `Planner`, `PlannerCapabilities`, and `PlanningResult` per ADRs 021–025.

### V3-101 — Architecture discriminator

Extend the architecture gate so Version 3 configs/results are explicit. Missing version remains Version 1; `2` remains frozen V2 semantics (ADR-016 preservation).

### V3-102 — Mechanism and search adapters

Wrap certified operating branches and planar 2R FK as a `RobotModel`. Wrap Dijkstra and A* as `Planner` adapters that declare capabilities and map `SearchResult` into `PlanningResult`.

### V3-103 — Compatibility fixture

Implement the single shared-Q compatibility fixture specified in the migration map. Agree on states, cost, selected goal, and shared instrumentation with the frozen V2 stack.

### V3-104 — Tests

Unit tests for serialization/round-trip of core types, adapter mapping, capability metadata, and the compatibility fixture. Preserve `tests/golden_v1` and V2 regressions.

## Exit criteria

1. Core interfaces importable and documented.
2. V1 and V2 architecture versions still behave as frozen.
3. Compatibility fixture passes.
4. No production campaign or obstacle sprint activated.
5. Hand off to V3.2 for the direct 2R Cartesian vertical slice.
