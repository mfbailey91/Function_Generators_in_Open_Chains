# Sprint V3.10 — Scene and Collision Framework

**Status:** drafted / not activated  
**Reserved work packages:** V3-1000–V3-1007  
**Code authorization:** none until Sprint V3.9 closes and ACTIVE_SPRINT explicitly activates V3.10  
**Depends on:** V3.9 cross-DOF free-space architecture closeout

## Sprint intent

Implement reusable collision-scene capability **without yet making mechanism-performance claims from obstacle routing**. Collision remains a `PlanningScene` concern; planners ask only whether states and continuous motions are valid.

## Non-goals

- obstacle-routing performance conclusions;
- MoveIt;
- production populations;
- dynamic obstacles or contact planning;
- mechanism-specific collision rules hidden in planners.

## Work packages

### V3-1000 — Collision-scene contract

Freeze frames, geometry ownership, state/motion collision semantics, tolerances, and instrumentation.

### V3-1001 — Planar robot geometry

Add simple link geometry for 2R/3R and deterministic obstacle primitives for visual debugging.

### V3-1002 — Spatial robot geometry

Add a minimal 6R spatial collision representation behind an adapter boundary compatible with a later mature collision backend.

### V3-1003 — World collision checks

Implement state collision checks with collision-pair provenance and counters.

### V3-1004 — Continuous motion collision validation

Validate local motions under an accepted interpolation/adaptive policy. Endpoint-only collision checks are insufficient.

### V3-1005 — Self-collision contract

Add self-collision pairs/exclusions where required and instrument them separately from world collision.

### V3-1006 — Frozen scene descriptors and visualization

Create named scene classes and visual diagnostics showing robot, obstacles, local motions, collision samples, and first invalid state.

### V3-1007 — Tests and framework closeout

Hand-worked collisions, grazing/tolerance cases, continuous-edge collisions, deterministic counters, and 2R/3R/6R scene smoke.

## Exit criteria

1. Existing planners require no planner-specific collision branches.
2. `PlanningScene.state_is_valid` and `motion_is_valid` remain the sole common validity interface.
3. Interior collision can invalidate a motion with valid endpoints.
4. Collision checks remain separate from planner-family exploration events.
5. Planar and spatial scene smoke is deterministic and visualizable.
6. No routing-performance claim is made until V3.11.
