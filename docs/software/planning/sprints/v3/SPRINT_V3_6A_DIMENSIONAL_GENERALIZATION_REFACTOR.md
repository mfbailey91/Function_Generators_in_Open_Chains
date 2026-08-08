# Sprint V3.6A — Dimensional-Generalization Refactor

**Status:** completed — dimensional-generalization refactor closed (V3-610–V3-617)
**Reserved work packages:** V3-610–V3-617
**Code authorization:** none (sprint closed; V3.6B remains drafted / not activated)
**Depends on:** Sprint V3.6 closeout; ADR-021–026
**Program:** [V3 pre-3R refactor and visual audit](../../V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md)
**Migration note:** [V3_6A_DIMENSIONAL_GENERALIZATION_MIGRATION.md](../../architecture/notes/V3_6A_DIMENSIONAL_GENERALIZATION_MIGRATION.md)

## Sprint intent

Remove known concrete planar-2R and operating-branch reach-throughs from shared
Version 3 architecture before adding a planar 3R robot.

This is a behavior-preserving refactor. It must not regenerate, overwrite, or
reinterpret frozen V1/V2/V3.5/V3.6 evidence.

## Non-goals

- implementing planar 3R FK or IK;
- changing V3.6 task or result semantics;
- adding new planner algorithms;
- adding obstacles, collision geometry, URDF, MoveIt, or production campaigns;
- reopening noninjective/full-cycle mechanisms;
- moving stable modules only to satisfy a target directory diagram.

## Work packages

### V3-610 — Sprint contract and compatibility baseline

Activate only this sprint. Record the pre-refactor test suite, optional-OMPL
environment, public imports, serialized fixtures, and representative V3.6 smoke
rows that must remain unchanged. Also record the provisional V3.7 package path
as a compatibility baseline. Do not regenerate frozen V3.6 or provisional V3.7
evidence.

### V3-611 — Generic kinematic-model protocol

Add a dimension-independent `KinematicModel` protocol with DOF, pose-valued
forward kinematics, and Jacobian operations. Adapt `Planar2R` without changing
its numerical behavior. Keep rendering/link-polyline methods outside the core
protocol.

### V3-612 — Generic operating-branch robot adapter

Replace the concrete `Planar2R` member in `OperatingBranchRobotModel` with a
generic kinematic model. Validate transmission-output dimension against
kinematic DOF. Remove `(2,)` shape gates from shared FK/Jacobian delegation.
Preserve the existing planar 2R factory as a compatibility wrapper.

### V3-613 — Robot-owned input-domain contract

Add a bounded input-domain object to `RobotModel` or a narrow companion protocol.
The initial domain exposes lower/upper bounds and periodic-axis metadata.
Migrate native sampling planners and OMPL state-space construction away from
`robot.branch.certificate` reach-through.

### V3-614 — Goal predicate/generator separation

Move planar 2R IK and elbow-family logic out of `core.goals`. Core retains
planner-independent goal predicates and generator protocols. Add compatibility
imports where necessary and preserve goal-candidate ordering/provenance.

### V3-615 — Shared trajectory and path metrics

Centralize waypoint/trajectory metrics for U, Q, and Cartesian paths. Preserve
declared integrated local-motion costs. Do not backfill or rewrite frozen result
packages.

### V3-616 — Three-dimensional architecture fixture

Add a synthetic 3D affine robot/transmission fixture that exercises physical
state construction, input-domain sampling, PRM, RRTConnect, tensor topology,
serialization, and OMPL round trip when available. This is not a 3R scientific
robot or evidence bank.

### V3-617 — Tests, migration note, and closeout

Add source-boundary tests and document the post-refactor ownership model.
Required static/behavior checks include:

- `core.goals` does not import `Planar2R`;
- shared sampling code does not access `.branch.certificate`;
- `OperatingBranchRobotModel` accepts a 3-DOF kinematic fixture;
- current 2R direct/lattice/native/OMPL smokes preserve status, selected goals,
  and objective costs;
- V1/V2 golden and V3.0–V3.6 suites remain green.

## Exit criteria

1. Shared robot, sampler, planner, and OMPL code obtains dimension and bounds
   through declared interfaces.
2. Planar 2R-specific IK lives outside the core goal contract.
3. The current planar 2R factories and public imports remain usable or have a
   documented compatibility shim.
4. A synthetic three-dimensional fixture passes native and optional-OMPL smoke
   tests without planner-specific task forks.
5. No frozen evidence artifact changes.
6. Sprint V3.6B remains blocked until the refactor is reviewed and green.

## Closeout

Completed. Migration ownership is recorded in
[`V3_6A_DIMENSIONAL_GENERALIZATION_MIGRATION.md`](../../architecture/notes/V3_6A_DIMENSIONAL_GENERALIZATION_MIGRATION.md).
ACTIVE_SPRINT marks V3.6A complete and leaves V3.6B drafted / not activated.
Frozen `results/v3_review/v3_6_*` and `v3_7_*` packages were not regenerated.
