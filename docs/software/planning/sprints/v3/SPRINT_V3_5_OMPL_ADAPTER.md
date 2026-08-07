# Sprint V3.5 — OMPL Adapter

**Status:** active — direct OMPL integration and native-planner parity
**Code authorization:** V3-500–V3-505 only
**Depends on:** [Sprint V3.4](SPRINT_V3_4_NATIVE_ROADMAP_TREE.md) (completed); accepted ADRs 021–026
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M5

## Sprint intent

Add OMPL as the first external planner backend while keeping Version 3 authoritative for physical state, \(U\rightarrow Q\rightarrow X\), goals, local motion, validity, objective semantics, result records, and benchmark classification. Validate the adapter against the existing free-space planar 2R native planners without introducing ROS, MoveIt, obstacles, higher-DOF robots, or population evidence.

## Entry conditions

1. V3.4 basic PRM/RRTConnect, seed protocol, exact-start handling, and ADR-026 pre-search classification are accepted and green.
2. ACTIVE_SPRINT explicitly activates V3.5.
3. ADR-025 remains the adapter boundary: OMPL is an algorithm backend, not the source of truth for mechanism state or metric semantics.

## Non-goals

- MoveIt, ROS, URDF/SRDF application integration;
- obstacle scenes or collision-scene campaigns;
- production Monte Carlo or free-space population inference;
- implementing every OMPL planner;
- reviving deferred native planner breadth from `V3-DEFER-001`;
- higher-DOF robots;
- changing frozen V1/V2 evidence or result semantics.

## Work packages

### V3-500 — Sprint contract and activation

Close V3.4, activate this contract, and authorize V3-500–V3-505 only.

### V3-501 — Optional dependency and environment gate

Introduce OMPL as an optional dependency. Tests that require OMPL must fail clearly when explicitly requested and skip cleanly in environments where the optional backend is not installed. Record the OMPL version and adapter configuration in result provenance.

### V3-502 — State-space and physical-state adapter

Map OMPL state coordinates to Version 3 `PhysicalState` through the existing `RobotModel`; do not let OMPL joint vectors replace \((u,q,\text{assembly_state})\) as physical identity. Initial scope is the certified monotonic planar 2R branch.

### V3-503 — Goal, validity, motion, and objective adapter

Map Version 3 goal predicates / goal sampling, state validity, continuous motion validation, and `ActuatorTravelObjective` into OMPL interfaces. Exact start remains exact. Any OMPL distance used for nearest-neighbor operations must be declared separately from the mechanism-aware optimization objective.

### V3-504 — Planner-data extraction and parity smoke

Run a bounded free-space smoke using a small OMPL planner subset chosen to overlap the native families (initially PRM-family and RRTConnect-family where available). Return `PlanningResult`, preserve ADR-026 task classes computed independently of planner outcome, and namespace OMPL-specific metrics / planner data without equating them to native graph expansions or tree extensions.

### V3-505 — Tests and compatibility gates

Test exact-start preservation, state round-trip, goal residuals, objective/path-cost agreement, validity delegation, seed/provenance behavior where supported, and bounded parity against native PRM/RRTConnect. Preserve V1/V2 golden suites and V3.1–V3.4 regressions.

## Exit criteria

1. At least one roadmap-family and one tree-family OMPL planner consume the same Version 3 `PlanningProblem` without planner-specific problem fields.
2. Version 3 `PhysicalState` remains authoritative at the adapter boundary; round-trip residuals are within documented tolerance.
3. Exact starts and Cartesian goal predicates retain ADR-023 semantics.
4. Mechanism-aware actuator-travel objective and continuous validity checks are delegated explicitly rather than replaced by ordinary joint distance.
5. OMPL-specific planner data are namespaced and are not compared as if identical to native family event counts.
6. A bounded parity smoke against native PRM/RRTConnect records status, selected goal, objective cost, task class, timings, and provenance.
7. Optional dependency behavior is documented and testable; absence of OMPL does not break the core package or frozen V1/V2 suites.
8. No MoveIt, obstacle, higher-DOF, population-evidence, or Monte Carlo work is activated opportunistically.
9. Hand off to V3.6 for the frozen free-space planner evidence bank.

## Deferred work

Native planner breadth intentionally omitted from V3.3/V3.4 remains in `V3-DEFER-001`. V3.5 may use OMPL equivalents for parity, but it does not silently close those native implementation items.
