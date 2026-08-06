# Sprint V3.4 — Native Roadmap and Tree Planners

**Status:** active — basic PRM and RRTConnect with frozen-seed reproducibility  
**Code authorization:** V3-400–V3-405 only  
**Depends on:** [Sprint V3.3](SPRINT_V3_3_LATTICE_LOCAL_MOTION.md) (completed); ADRs 021–026  
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M4 (narrowed)

## Sprint intent

Deliver the first Version 3 sampling-based planners on the shared `PlanningProblem`: basic PRM and RRTConnect in free space, with a common seed/repetition protocol, exact starts, ADR-026 classification, and namespaced roadmap/tree metrics—without Lazy/PRM*/RRT*, OMPL, obstacles, or Monte Carlo.

## Entry conditions

1. V3.3 lattice connectivity, integrated edge cost, and exact-start overlay are accepted and green.
2. ACTIVE_SPRINT explicitly activates V3.4.
3. Exact-start semantics follow ADR-023 (no task-semantic `start_tolerance`).

## Non-goals

- Lazy PRM, PRM*, plain RRT, RRT*;
- BIT*/FMT* and other informed/batch planners;
- OMPL adapter (V3.5);
- free-space evidence bank / population strata (V3.6);
- obstacle scenes (V3.7);
- amortized multi-query population claims;
- moving `GraphSearchPlanner` into `planners/lattice/`;
- production Monte Carlo / Experiment A reinterpretation.

## Work packages

### V3-400 — Sprint contract and activation

Author this contract; close V3.3; authorize V3-400–V3-405 only.

### V3-401 — Seed and repetition protocol

Shared NumPy RNG helper; record seed and repetition index in result provenance/metrics. V3.4 smoke uses one repetition per task.

### V3-402 — Native PRM

Basic PRM: sample in certified actuator box, connect with validated local motion, attach exact start and goal candidates, Dijkstra on the roadmap. Report preprocess vs query timing and `planner_metrics["roadmap"]`.

### V3-403 — Native RRTConnect

Bidirectional RRT-Connect from exact start and a selected goal state. Report `planner_metrics["tree"]` (iterations, extensions, NN ops; rewires fixed at 0).

### V3-404 — Smoke pack

Paired four-bar / span-matched gearbox free-space smoke with Cartesian disks, frozen seeds, both planners, and ADR-026 `task_class` on every result.

### V3-405 — Tests

Seed reproducibility, invalid/already-satisfied paths, motion rejection, exact-start preservation, namespaced metrics, and V3.2/V3.3 regression.

## Exit criteria

1. The same `PlanningProblem` is solved by PRM and RRTConnect without problem-type forks.
2. Exact starts are preserved (no start-tolerance task semantics).
3. Frozen seed reproduces smoke outcomes under the declared one-repetition contract.
4. Roadmap preprocess and query times are reported separately.
5. Family metrics are namespaced under `roadmap` / `tree`.
6. Free-space only; existing V3 suites remain green.
7. No OMPL / obstacles / Monte Carlo / Lazy·PRM* / RRT* activated opportunistically.
8. Hand off to V3.5 for the OMPL adapter.
