# ADR-021 — Version 3 planning problem contract

**Status:** Proposed  
**Applies to:** Version 3  
**Related:** ADR-014, ADR-015, ADR-019, ADR-020; [V3_PROJECT_PLAN.md](../../V3_PROJECT_PLAN.md); Sprint V3.0 V3-002  
**Supersedes:** nothing (Version 2 graph-experiment contracts remain authoritative for frozen V2 evidence)

## Context

Version 2 successfully isolated mechanism effects inside a graph-centered experiment stack. That stack fused robot task definition, lattice representation, local motion, objective, planner, and benchmark protocol in shared runners. Version 3 must ask mechanism questions across planner families without carrying those fusions forward as universal assumptions.

## Decision

Adopt a planner-independent planning problem as the Version 3 software center:

```python
@dataclass(frozen=True)
class PlanningProblem:
    robot: RobotModel
    scene: PlanningScene
    start: PhysicalState
    goal: GoalConstraint
    path_constraints: ConstraintSet
    local_motion: LocalMotionModel
    objective: PlanningObjective
```

### Physical state

```python
@dataclass(frozen=True)
class PhysicalState:
    u: NDArray[np.float64]
    q: NDArray[np.float64]
    branch_id: str | None = None
    auxiliary_state: Mapping[str, Any] = field(default_factory=dict)
```

On a certified monotonic branch, \(u = g_m^{-1}(q)\) is unique. The explicit `u` field remains because objectives, diagnostics, and later noninjective mechanisms require it.

### Robot model

```python
class RobotModel(Protocol):
    @property
    def dof(self) -> int: ...

    def input_to_output(self, u) -> NDArray[np.float64]: ...
    def output_to_inputs(self, q) -> Sequence[NDArray[np.float64]]: ...
    def forward_kinematics(self, state: PhysicalState) -> Pose: ...
    def jacobian_q_to_x(self, state: PhysicalState) -> NDArray[np.float64]: ...
    def state_within_limits(self, state: PhysicalState) -> bool: ...
```

### Goal, scene, local motion, objective, planner, result

- `GoalConstraint` is a task predicate (`satisfied`, `residual`, `sample_candidates`), not necessarily one configuration.
- `PlanningScene` validates states and continuous local motions.
- `LocalMotionModel.connect` returns a continuous motion or `None`.
- `PlanningObjective` evaluates trajectories; endpoint Euclidean cost is allowed only after calibrated approximation at the connection scale.
- `Planner.solve(problem) -> PlanningResult` is the sole planner entry; problem definitions must not contain planner-specific fields.
- `PlanningResult` carries status, trajectory, selected goal state, wall time, objective cost, path lengths in \(U\)/\(Q\)/\(X\), validity-check counts, task class, residual, namespaced `planner_metrics`, and provenance.

Keep the following eight concepts independent: physical state, task, planning representation, local motion, validity, objective, planner, and benchmark protocol. No experiment runner may define all eight internally.

## Consequences

- Direct, lattice, roadmap, tree, OMPL, and later MoveIt backends consume the same problem type.
- Version 2 runners remain historical; they are not the Version 3 problem API.
- Implementation begins in Sprint V3.1 only after this ADR is accepted.
- No production Monte Carlo, obstacle framework, OMPL, or MoveIt dependency is authorized by this ADR alone.

## Non-goals

- Source-module reorganization to the target tree in the V3 plan.
- API breaks to frozen Version 2 configs or golden fixtures.
- Redefining Version 2 Experiment A or B estimands.
