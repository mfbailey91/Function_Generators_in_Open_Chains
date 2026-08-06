# Sprint V3.2 — Direct 2R Cartesian Vertical Slice

**Status:** drafted / not activated  
**Code authorization:** none until this sprint is explicitly activated after V3.1 exit  
**Depends on:** [Sprint V3.1](SPRINT_V3_1_CORE_PROBLEM_RESULT_MODEL.md); ADRs 021–026  
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M2

## Sprint intent

Deliver the first Version 3 application vertical slice: planar 2R, exact start, Cartesian position goal region, output-linear and input-linear direct planners, task classification, and the common result schema—without lattice redesign, sampling-based planners, or obstacles.

## Entry conditions

1. V3.1 core interfaces, adapters, and compatibility fixture are accepted and green.
2. ACTIVE_SPRINT explicitly activates V3.2.
3. Exact-start and goal-region semantics follow ADR-023 (no task-semantic `start_tolerance`).

## Non-goals

- eight-connected lattice implementation (V3.3);
- PRM/RRT/OMPL (V3.4–V3.5);
- obstacle scenes (V3.7);
- 3R or higher DOF;
- population Monte Carlo / production inference;
- reinterpreting Experiment A or frozen Experiment B packages as V3 application results.

## Work packages

### V3-200 — Planar 2R robot model

Expose a Version 3 `RobotModel` for the certified monotonic 2R transmission + planar FK path used in free-space studies.

### V3-201 — Exact start and Cartesian disk goal

Build tasks with exact `PhysicalState` starts and planar position goal disks. Record residuals, IK-family descriptors, and selected goal state per ADR-023/026.

### V3-202 — Direct planners

Implement output-linear and input-linear direct planners as first `Planner` backends. Classify each mechanism-task instance under ADR-026 **before** any comparative search: already satisfied, direct/local feasible, direct connector unavailable (invites nonlocal planners later), invalid/unrepresentable, or certifiably unreachable. Do not use the informal label “global planning required.”

### V3-203 — Free-space scene

Provide a free-space `PlanningScene` with mechanism and joint limits only.

### V3-204 — Result schema and smoke evidence

Emit `PlanningResult` records with common metrics. Add a small deterministic smoke pack (not a population study) that exercises both direct planners on paired mechanisms.

### V3-205 — Tests

Parity tests for direct connectors, classification, exact-start handling, and result provenance. Continue V1/V2 regression suites.

## Exit criteria

1. Exact-start Cartesian disk tasks solve through both direct planners where classification predicts direct feasibility.
2. Task classification is recorded for every smoke task.
3. Common metrics and selected goal states are present in results.
4. No lattice/roadmap/tree/OMPL work has been activated opportunistically.
5. Hand off to V3.3 for lattice and local-motion validation.
