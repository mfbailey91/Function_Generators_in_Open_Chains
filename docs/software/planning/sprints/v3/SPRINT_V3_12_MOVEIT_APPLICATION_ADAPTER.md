# Sprint V3.12 — MoveIt Application Adapter

**Status:** drafted / not activated  
**Reserved work packages:** V3-1200–V3-1207  
**Code authorization:** none until Sprint V3.11 closes and ACTIVE_SPRINT explicitly activates V3.12  
**Depends on:** V3.8 6R spatial model, V3.10 collision contract, V3.11 obstacle-routing evidence

## Sprint intent

Add MoveIt as an **application integration layer**, not as the source of truth for Version 3. Initial scope is the certified monotonic regime where \(q\) uniquely identifies the actuator-side realization.

## Non-goals

- representing globally noninjective hidden mechanism state inside ordinary URDF joint identity;
- replacing V3 objectives with default MoveIt joint distance;
- making MoveIt mandatory for core tests;
- production populations.

## Work packages

### V3-1200 — Compatibility boundary

Define which `PlanningProblem`s can be losslessly exported and which must be rejected.

### V3-1201 — URDF/SRDF robot adapter

Map selected standard 6R application models while retaining V3 mechanism metadata outside ordinary joint identity.

### V3-1202 — Planning-scene bridge

Translate world/self-collision scenes and verify collision-status parity on frozen states/motions.

### V3-1203 — Goal/constraint bridge

Translate compatible position, orientation, full-pose, and path constraints with explicit frames/tolerances.

### V3-1204 — Objective/result bridge

Recover trajectories into authoritative V3 `PhysicalState`s and reevaluate mechanism-aware actuator cost. Do not misrepresent a pipeline as optimizing the V3 objective when it does not.

### V3-1205 — Pipeline subset

Exercise selected OMPL, Pilz, CHOMP, and/or STOMP pipelines as application references; metrics remain namespaced.

### V3-1206 — Parity tasks

Reproduce selected free-space and obstacle tasks already solved by the native/direct-OMPL V3 stack.

### V3-1207 — Tests and closeout

Frame/tolerance parity, collision parity, state round trips, objective reevaluation, unsupported-problem rejection, and review artifact.

## Exit criteria

1. MoveIt remains optional and outside the core dependency set.
2. Unsupported mechanism-state semantics are rejected rather than projected away.
3. Returned trajectories reconstruct as valid V3 physical states.
4. Scene/task tolerances are auditable across the adapter.
5. Application-facing results are not confused with native objective guarantees.
