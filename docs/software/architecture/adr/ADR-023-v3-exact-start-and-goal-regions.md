# ADR-023 — Version 3 exact start and goal-region contract

**Status:** Proposed  
**Applies to:** Version 3  
**Related:** ADR-019, ADR-020, ADR-021, ADR-022; Sprint V3.0 V3-004  
**Amends for Version 3:** task-semantic use of `start_tolerance` from ADR-019 / Experiment B  
**Does not rewrite:** ADR-019/020 authority for frozen Version 2 smoke and calibration evidence

## Context

Experiment B introduced Cartesian goal disks and attached sampled Cartesian starts to lattice nodes within `start_tolerance`. That tolerance is a discrete-graph attachment approximation. A robot application has a known physical start state. Goal tolerance is a real task parameter and must not be confused with start attachment.

## Decision

### Exact start

The start is an exact known `PhysicalState`. It is never a Cartesian tolerance region.

- Roadmap and lattice planners attach the exact start through a temporary query state and validated local connectors.
- Tree planners use the exact start as the root.
- A numerical attachment residual may be reported as an algorithm diagnostic.
- `start_tolerance` is **not** a Version 3 task parameter.

### Goal regions

Goals are `GoalConstraint` predicates. Initial Version 3 types include exact output configuration, output-joint regions, planar Cartesian position disks, planar pose regions, spatial position spheres, orientation tolerances, full \(SE(3)\) pose regions, and partial-pose / pointing constraints for underactuated arms.

Goal tolerance must be identical across paired mechanisms. Do not tune tolerance per mechanism to equalize graph-node counts.

### Reporting

Every successful plan reports, where meaningful:

- represented goal-state count (or measure descriptor);
- IK families represented;
- final Cartesian (or task) residual;
- selected goal `PhysicalState`;
- direct-connector availability.

### Relation to Version 2

ADR-020 goal-set search remains the Version 2 exact-search contract for frozen Experiment B packages. Version 3 planners may reuse that core through adapters when the representation is a discrete graph, but the external problem always supplies an exact start and a goal predicate.

## Consequences

- Cartesian task banks sample goals and exact starts in task/physical coordinates; attachment is planner-backend logic.
- Compatibility fixtures must distinguish V2 nearest-node attachment residuals from V3 exact-start semantics when comparing instrumentation.
- Experiment B production promotion remains held; this ADR does not authorize it.

## Non-goals

- Changing frozen V2.12 smoke/calibration configs.
- Implementing IK-family balancing in V3.0.
