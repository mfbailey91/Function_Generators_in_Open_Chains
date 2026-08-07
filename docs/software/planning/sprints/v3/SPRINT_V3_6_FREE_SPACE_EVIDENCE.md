# Sprint V3.6 — Free-Space Planner Evidence

**Status:** active — bounded free-space evidence bank across delivered planner families
**Code authorization:** V3-600–V3-605 only
**Depends on:** [Sprint V3.5](SPRINT_V3_5_OMPL_ADAPTER.md) (completed); accepted ADRs 021–026
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M6

## Sprint intent

Publish a **frozen external Cartesian** free-space task bank and run the already-delivered planner families (direct, lattice Dijkstra, native PRM/RRTConnect, OMPL when available) under ADR-026 pre-search classification and size strata. Produce a tracked review artifact. This is **not** population inference, Monte Carlo, or an obstacle study.

## Entry conditions

1. V3.5 OMPL adapter, corrective contract, and `results/v3_review/v3_5_closeout/` are accepted.
2. ACTIVE_SPRINT explicitly activates V3.6.
3. No new planner algorithms are required; V3.6 consumes delivered planners only.

## Non-goals

- Obstacles / collision scenes (V3.7);
- MoveIt, higher-DOF, production Monte Carlo;
- Closing `V3-DEFER-001` native breadth (Lazy-PRM, PRM*, RRT*, …);
- Reinterpreting frozen V2 evidence;
- Claiming bank means equal population estimands.

## Work packages

### V3-600 — Sprint contract and activation

Author this contract; authorize V3-600–V3-605 only.

### V3-601 — Frozen Cartesian task bank

Versioned JSON bank `configs/v3/free_space_planar2r_v1.json` with external tip centers/radii and start U-fractions; loader builds paired four-bar / gearbox `PlanningProblem`s.

### V3-602 — Classification and size strata

ADR-026 per-mechanism task class before search; paired strata; tip-separation size bins; pre-search descriptors.

### V3-603 — Multi-planner evidence runner

Same bank × mechanisms × planner families; OMPL rows skip cleanly when bindings are absent.

### V3-604 — Review artifact

Tracked package under `results/v3_review/v3_6_free_space/` plus HTML printout. Not a population study.

### V3-605 — Tests and gates

Bank load, strata determinism, runner columns, OMPL skip path; preserve V1–V3.5 suites.

## Exit criteria

1. Frozen bank is versioned and loadable without editing Python smoke catalogs.
2. Every evidence row records ADR-026 `task_class`, size stratum, and paired stratum when applicable.
3. Delivered planner families run on the same external tasks (OMPL optional).
4. Review artifact records revision, seed, and row-level JSON.
5. No population inference or obstacle work is activated.
6. Hand off to V3.7 only after free-space semantics are reviewed.

## Deferred work

`V3-DEFER-001` remains open. Obstacle framework is Sprint V3.7.
