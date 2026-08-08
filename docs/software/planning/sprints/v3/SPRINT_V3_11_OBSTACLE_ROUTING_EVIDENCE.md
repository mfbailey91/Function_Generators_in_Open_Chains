# Sprint V3.11 — Obstacle Routing Evidence

**Status:** drafted / not activated  
**Reserved work packages:** V3-1100–V3-1106  
**Code authorization:** none until Sprint V3.10 closes and ACTIVE_SPRINT explicitly activates V3.11  
**Depends on:** V3.10 scene/collision framework; accepted 2R/3R/6R free-space baselines

## Sprint intent

Introduce obstacle topology as a controlled factor after the dimensional free-space architecture is closed. `direct connector unavailable` now becomes a scientifically important ADR-026 stratum rather than something to manufacture in free space.

## Scene classes

At minimum include frozen variants of:

- direct path still clear (negative control);
- one blocking obstacle;
- offset obstacle with two route families;
- narrow passage;
- obstacle near one IK/goal family;
- spatial scene with alternative approach/orientation routes.

## Work packages

### V3-1100 — Obstacle task/scene bank

Freeze shared physical starts, task goals, scene geometry, and route-class metadata.

### V3-1101 — Collision-aware preclassification

Record per-mechanism direct-connector collision status, first blocking constraint, represented-goal coverage, and paired direct-feasibility strata.

### V3-1102 — Planner portfolio

Run an agreed subset of lattice/roadmap/tree/OMPL planners appropriate to each dimension. Do not expand native planner breadth merely to fill a table.

### V3-1103 — Route diagnostics

Record route-family labels where robustly definable, clearance, selected goal family, actuator cost, output/Cartesian path lengths, and collision-check counts.

### V3-1104 — Paired mechanism effects

Compare nonlinear transmission against matched gearbox on identical start, goal, and scene. Report absolute and paired effects within task/scene strata.

### V3-1105 — Stochastic repetitions

Freeze seed sets/process-isolation rules and separate first-solution from optimizing behavior where relevant.

### V3-1106 — Evidence report

Answer separately whether the mechanism changes direct feasibility, route selection, actuator cost along comparable routes, and planner effort after controlling task/route class.

## Exit criteria

1. At least one bank contains genuine collision-caused `direct connector unavailable` tasks.
2. Negative-control scenes reproduce free-space behavior.
3. Route/task strata are declared before aggregate planner effects.
4. Mechanism effects are not conflated with different starts/goals/scenes.
5. Collision and planner-specific exploration metrics remain separate.
6. Results are reviewed before MoveIt integration.
