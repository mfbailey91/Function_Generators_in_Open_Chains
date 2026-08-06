# ADR-024 — Version 3 local motion and cost contract

**Status:** Proposed  
**Applies to:** Version 3  
**Related:** ADR-015, ADR-017, ADR-021; Sprint V3.0 V3-005  
**Supersedes for Version 3:** treating four-connected lattice adjacency as the definition of physical motion

## Context

Historical Experiment A graphs permitted one coordinate to change at a time. That four-connected stencil introduced staircase paths, grid-orientation effects, and tie degeneracy. Edge costs often used endpoint Euclidean displacement in actuator space. Version 3 needs continuous local motion independent of lattice indexing, with mechanism-aware integrated cost.

## Decision

### Continuous local motion

A local motion is a continuous curve \(\gamma:[0,1]\rightarrow\mathcal S\) produced by a `LocalMotionModel`. Graph adjacency selects candidate neighbors; it does not define the continuous robot motion.

Initial connectors:

1. **Output-linear:** \(q(t)=(1-t)q_a+t q_b\), with \(u(t)=g_m^{-1}(q(t))\).
2. **Input-linear:** \(u(t)=(1-t)u_a+t u_b\), with \(q(t)=g_m(u(t))\).
3. **Cartesian-linear with IK continuation** — later.

State and motion validity are continuous checks through `PlanningScene`.

### Mechanism-aware cost

The initial shared objective is actuator-path length

\[
J_U[\gamma]=\int_0^1\left\|\frac{du(t)}{dt}\right\|_2\,dt.
\]

For a shared output-space connector, each mechanism assigns a different cost to the same visible \(q(t)\) through its inverse map. Required objective families include actuator, output-joint, and Cartesian path lengths, plus later time/energy/clearance terms.

Endpoint Euclidean distance may approximate integrated local cost only when a calibration demonstrates adequacy at the selected connection scale.

### Lattice baseline

The first Version 3 lattice baseline permits simultaneous joint movement. For planar 2R this means an eight-connected stencil, not the historical four-connected one-coordinate-at-a-time stencil. Connectivity is planner configuration, not part of the robot model. Four-connectivity remains a historical and diagnostic ablation.

## Consequences

- Direct input-linear paths between exact endpoints provide free-space reference bounds for optimizing planners.
- V2 four-connected production evidence stays frozen under its declared formulation.
- Integrated edge-cost implementations land with lattice work (V3.3), not in V3.0 docs-only sprint.

## Non-goals

- Implementing eight-connected search in V3.0.
- Declaring endpoint costs obsolete for frozen V2 configs.
