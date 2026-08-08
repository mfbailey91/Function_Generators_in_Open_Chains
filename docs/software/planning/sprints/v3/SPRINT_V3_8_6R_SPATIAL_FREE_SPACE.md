# Sprint V3.8 — 6R Spatial Free-Space Planning

**Status:** drafted / not activated  
**Reserved work packages:** V3-800–V3-807  
**Code authorization:** none until Sprint V3.7 closes and ACTIVE_SPRINT explicitly activates V3.8  
**Depends on:** V3.7 3R planar free-space closeout; ADR-021–026

## Sprint intent

Build an idealized 6R serial manipulator directly in the V3 kinematics layer and demonstrate free-space spatial planning with the same physical-state, goal, local-motion, objective, classification, and planner interfaces already used in 2R/3R.

This sprint deliberately separates **spatial kinematics** from **MoveIt/URDF/collision integration**.

Required task families:

1. spatial position region, \(p\in\mathbb R^3\);
2. full pose region, \(G\in SE(3)\).

## Non-goals

- world obstacles or self-collision;
- URDF/SRDF or MoveIt;
- forcing a six-dimensional tensor lattice;
- 4R/5R partial tasks;
- production populations;
- dynamics or torque-limited planning.

## Work packages

### V3-800 — Spatial serial-kinematics contract

Add a generic fixed-screw 6R serial model, preferably product-of-exponentials. Preserve the distinction between actuator coordinates \(u\), generalized output coordinates \(q\), and spatial pose \(G\).

### V3-801 — 6R paired mechanism arms

Compose six certified scalar transmission modules into paired mechanism-aware robots over a bounded monotonic \(Q\) domain.

### V3-802 — Spatial goal predicates

Implement position-sphere and \(SE(3)\) pose-region residuals with explicit translation/orientation tolerances and frame conventions.

### V3-803 — Numerical IK / goal generation

Introduce deterministic multi-start numerical IK as a goal-generation service, not task semantics. Freeze starts/seeds, deduplicate solutions, and record provenance. Stored benchmark targets are spatial task descriptors rather than planner-visible hidden target \(q\) values.

### V3-804 — Higher-dimensional planner subset

Use direct input-linear reference, native RRTConnect/PRM where scientifically useful, and OMPL RRTConnect/PRM. A dense lattice is diagnostic-only and not an exit criterion.

### V3-805 — Frozen 6R free-space bank

Create shared starts and spatial position/full-pose goals with represented-goal coverage, IK diagnostics, direct reference cost, and size descriptors.

### V3-806 — 6R review artifact

Report feasibility, goal coverage, planner status, suboptimality to direct reference, total wall time, validity calls, and paired mechanism effects. Keep position and full-pose results separate.

### V3-807 — Tests and closeout

POE/FK hand cases, Jacobian finite differences, state consistency, shared starts, orientation residuals, IK determinism, goal satisfaction, and planner-adapter round trips.

## Exit criteria

1. The core V3 `PlanningProblem` requires no 6R-specific fields.
2. Spatial `PhysicalState` remains authoritative under \(U\rightarrow Q\).
3. Position and full-pose tasks require no collision or MoveIt dependency.
4. Numerical IK is reproducible and separate from the goal predicate.
5. At least direct reference, one native sampling planner, and one OMPL planner solve the same bounded spatial problems.
6. No six-dimensional tensor-lattice requirement is introduced for historical continuity.
7. V3.9 remains blocked until 6R free-space evidence is reviewable.
