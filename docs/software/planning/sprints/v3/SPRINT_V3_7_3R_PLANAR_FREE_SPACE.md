# Sprint V3.7 — 3R Planar Free-Space Planning

**Status:** drafted / not activated  
**Reserved work packages:** V3-700–V3-706  
**Code authorization:** none until Sprint V3.6 closes and ACTIVE_SPRINT explicitly activates V3.7  
**Depends on:** corrected Sprint V3.6 2R free-space evidence; ADR-021–026

## Sprint intent

Extend the validated free-space formulation from planar 2R position planning to planar 3R while changing as little else as possible.

Required task families:

1. **position-only:** Cartesian disk goals in \((x,y)\), leaving one redundant degree of freedom;
2. **full planar pose:** bounded regions in \((x,y,\phi)\in SE(2)\).

The purpose is to validate redundant goal sets, multiple IK families, exact physical starts, mechanism-aware actuator cost, and planner-family behavior in one additional dimension before collision geometry is introduced.

## Non-goals

- obstacles, self-collision, or world collision;
- 4R/5R partial spatial tasks;
- 6R spatial kinematics;
- MoveIt or URDF integration;
- production Monte Carlo;
- reopening full-cycle/noninjective mechanisms.

## Work packages

### V3-700 — 3R task semantics

Freeze position-only and \(SE(2)\) pose predicates, orientation wrapping/tolerance, exact-start semantics, and represented-goal reporting.

### V3-701 — Planar 3R robot and mechanism composition

Add a generic planar 3R serial `RobotModel` using three certified scalar transmission modules. Preserve \(\mathcal U\rightarrow\mathcal Q\rightarrow\mathcal X\) and build paired nonlinear-transmission / span-matched gearbox arms over one shared \(Q\) domain.

### V3-702 — Goal generation and redundancy

Implement deterministic goal generation for full pose and for position-only redundant goals using a frozen representation policy over the free orientation coordinate. Keep the physical predicate separate from the represented goal set.

### V3-703 — Planner adapters in 3D state space

Run delivered direct, native roadmap/tree, and OMPL planners without planner-specific task semantics. A small 3D lattice may remain diagnostic (26-connected Chebyshev-radius-one) where practical; it is not a production requirement.

### V3-704 — Frozen 3R free-space task bank

Create a small external bank with shared physical starts, both task families, task-size descriptors, and represented redundancy/IK provenance.

### V3-705 — 3R evidence artifact

Report common status, direct represented-goal reference cost, planner suboptimality, total wall time and phase timings, represented goal coverage, and paired mechanism \(\Delta J\). Keep position-only and full-pose estimands separate.

### V3-706 — Tests and closeout

FK/Jacobian consistency, shared starts, pose-angle residuals, redundant goal determinism, direct-reference bounds, and native/OMPL task-class parity.

## Exit criteria

1. One `PlanningProblem` contract supports both 3R position-only and full \(SE(2)\) pose goals.
2. Exact starts remain shared in \(Q\)/Cartesian state across paired mechanisms.
3. Position-only goals exercise a documented redundant represented goal set rather than one arbitrary orientation.
4. Full-pose goals preserve orientation tolerance/wrapping semantics.
5. Delivered planners consume the same goal representation or an explicitly declared continuous goal interface.
6. Direct represented-goal reference costs exist for planner-suboptimality interpretation.
7. No collision geometry is required for the sprint to pass.
8. V3.8 remains blocked until both task families are reproducible and reviewed.
