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

1. **Output-linear:** \(q(t)=(1-t)q_a+t q_b\), lifted through the physical mechanism state to obtain \(u(t)\).
2. **Input-linear:** \(u(t)=(1-t)u_a+t u_b\), with \(q(t)=g_m(u(t))\).
3. **Cartesian-linear with IK continuation** — later.

On the initial certified monotonic branches, the output-linear lift is the unique inverse \(u(t)=g_m^{-1}(q(t))\). When noninjective maps return, it must be a branch-preserving continuation from the start `PhysicalState`; pointwise inverse lookup may not jump between preimages or assembly sheets.

State and motion validity are continuous checks through `PlanningScene`.

### Mechanism-aware cost

The initial shared objective is actuator-path length

\[
J_U[\gamma]=\int_0^1\left\|\frac{du(t)}{dt}\right\|_2\,dt.
\]

For a shared output-space connector, each mechanism assigns a different cost to the same visible \(q(t)\) through its lifted inverse map. Required objective families include actuator, output-joint, and Cartesian path lengths, plus later time/energy/clearance terms.

Endpoint formulas have connector-specific meaning:

- For input-linear motion under Euclidean actuator length,

  \[
  J_U[\gamma]=\|u_b-u_a\|_2,
  \]

  so endpoint Euclidean distance is exact.

- For output-linear motion through a nonlinear inverse, endpoint actuator distance is generally only a lower bound on the connector arc length and must not replace integration without a demonstrated approximation contract.

- For arbitrary connectors and objectives, the cost implementation must declare whether it is analytic, numerically integrated, or calibrated as an endpoint approximation at the selected connection scale.

### Free-space reference bounds

For fixed actuator endpoints in unconstrained Euclidean \(\mathcal U\), the input-linear path realizes the global path-length lower bound:

\[
J_U^*=\|u_g-u_s\|_2.
\]

For a goal region \(\mathcal G\), the appropriate lower bound is

\[
\inf_{s\in\mathcal G}
\|u(s)-u_s\|_2,
\]

evaluated over certified physical goal states or a documented lower-bounding relaxation. The direct distance to one planner-selected goal state is not a universal lower bound for the entire goal region.

### Lattice baseline

The first Version 3 lattice baseline permits simultaneous joint movement. For planar 2R this means an eight-connected stencil, not the historical four-connected one-coordinate-at-a-time stencil. Connectivity is planner configuration, not part of the robot model. Four-connectivity remains a historical and diagnostic ablation.

## Consequences

- Direct input-linear paths between fixed exact endpoints provide exact free-space reference bounds for Euclidean actuator length.
- Goal-region bounds are minimized over the region rather than tied to one selected goal state.
- Output-linear connectors preserve physical branch identity.
- V2 four-connected production evidence stays frozen under its declared formulation.
- Integrated edge-cost implementations land with lattice work (V3.3), not in V3.0 docs-only sprint.

## Non-goals

- Implementing eight-connected search in V3.0.
- Declaring endpoint costs obsolete for frozen V2 configs.
