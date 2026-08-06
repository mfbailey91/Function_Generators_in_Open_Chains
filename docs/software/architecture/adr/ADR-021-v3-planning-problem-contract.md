# ADR-021 — Version 3 planning problem contract

**Status:** Accepted  
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
    assembly_state: Mapping[str, Any] = field(default_factory=dict)
    auxiliary_state: Mapping[str, Any] = field(default_factory=dict)
```

On a certified monotonic branch, \(u = g_m^{-1}(q)\) is unique. The explicit `u` field remains because objectives, diagnostics, and later noninjective mechanisms require it.

A `PhysicalState` is valid only when all redundant coordinates describe the same mechanism state:

\[
\left\|q-g_m(u,\text{assembly state})\right\|
\le \epsilon_{\mathrm{state}}.
\]

Callers must not construct unchecked physical states and then allow one subsystem to read \(u\) while another reads an inconsistent \(q\). States are created or certified through `RobotModel`.

### Robot model

```python
@dataclass(frozen=True)
class StateCandidate:
    state: PhysicalState
    residual: float
    provenance: Mapping[str, Any] = field(default_factory=dict)


class RobotModel(Protocol):
    @property
    def dof(self) -> int: ...

    def state_from_input(
        self,
        u,
        assembly_state: Mapping[str, Any] | None = None,
    ) -> PhysicalState: ...

    def states_from_output(
        self,
        q,
    ) -> Sequence[StateCandidate]: ...

    def validate_state(
        self,
        state: PhysicalState,
        tolerance: float,
    ) -> bool: ...

    def forward_kinematics(self, state: PhysicalState) -> Pose: ...
    def jacobian_q_to_x(self, state: PhysicalState) -> NDArray[np.float64]: ...
    def state_within_limits(self, state: PhysicalState) -> bool: ...
```

`states_from_output` returns complete branch-bearing physical candidates rather than actuator vectors alone. This preserves assembly state, inverse residual, and provenance for later noninjective mechanisms.

### Conceptual supporting types

The following names are conceptual contracts for Version 3. Detailed serialization lands in Sprint V3.1; ADRs may use these sketches without freezing JSON schemas.

```python
@dataclass(frozen=True)
class GoalResidual:
    """Task-space residual of a physical state against a goal predicate.

    For a planar position disk the primary scalar is Cartesian distance to the
    goal center (or signed distance to the disk). Vector components and named
    extras (orientation error, pointing error) are goal-family specific.
    """

    primary: float
    components: NDArray[np.float64] | None = None
    extras: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalMotion:
    """Continuous motion ``gamma: [0, 1] -> PhysicalState`` with declared endpoints.

    Concrete carriers may store analytic parameters, sampled waypoints, or an
    adapter handle. Validity and cost consume the motion object, not lattice indices.
    """

    start: PhysicalState
    end: PhysicalState
    model_id: str
    # parameterization is model-specific; not part of the problem definition


@dataclass(frozen=True)
class GoalSamplingRequest:
    """Parameters for generating physical goal candidates from a goal predicate.

    Separates IK / discretization / sampling policy from task semantics.
    """

    max_candidates: int
    seed: int | None = None
    representation_hint: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)


# Cost is an ordered scalar or structured objective value with planner-declared
# comparison. Scalar float is sufficient for the initial actuator-path studies;
# structured costs must still expose ``is_better`` via IncrementalPlanningObjective.
Cost = float
```

### Goal predicates and candidate generation

`GoalConstraint` defines task semantics only:

```python
class GoalConstraint(Protocol):
    def satisfied(self, state: PhysicalState) -> bool: ...
    def residual(self, state: PhysicalState) -> GoalResidual: ...
```

Candidate generation is a separate service:

```python
class GoalStateGenerator(Protocol):
    def generate(
        self,
        robot: RobotModel,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> Sequence[StateCandidate]: ...
```

This separation prevents a task predicate from silently choosing an IK family, discretization, or planner-specific sampling strategy. A valid goal region may exist even when no candidate generator is available.

### Scene, local motion, objective, planner, and result

- `PlanningScene` validates states and continuous local motions.
- `LocalMotionModel.connect` returns a continuous `LocalMotion` or `None`.
- `PlanningObjective` evaluates complete trajectories.
- An objective used by an incremental or optimizing planner must additionally define compatible motion-cost composition and, when A* or another informed method is used, a documented lower bound.
- `Planner.solve(problem) -> PlanningResult` is the sole planner entry; problem definitions must not contain planner-specific fields.
- `PlanningResult` carries status, trajectory, selected goal state, timing decomposition, objective cost, path lengths in \(U\)/\(Q\)/\(X\), validity-check counts, task class, residual, namespaced `planner_metrics`, and provenance.

A minimal incremental objective contract is:

```python
class IncrementalPlanningObjective(PlanningObjective, Protocol):
    def identity_cost(self) -> Cost: ...
    def motion_cost(self, motion: LocalMotion) -> Cost: ...
    def combine(self, prefix: Cost, edge: Cost) -> Cost: ...
    def is_better(self, a: Cost, b: Cost) -> bool: ...
    def cost_to_go_lower_bound(
        self,
        state: PhysicalState,
        goal: GoalConstraint,
    ) -> Cost: ...
```

A planner may reject an otherwise valid `PlanningProblem` when the selected objective does not provide the algebra or lower bound that planner requires. Heuristic and edge-cost compatibility must never be inferred from unrelated Euclidean coordinates.

Keep the following eight concepts independent: physical state, task, planning representation, local motion, validity, objective, planner, and benchmark protocol. No experiment runner may define all eight internally.

## Consequences

- Direct, lattice, roadmap, tree, OMPL, and later MoveIt backends consume the same problem type.
- Physical-state invariants are checked at construction or adapter boundaries.
- Goal semantics remain independent of IK and candidate-generation policy.
- Search algorithms declare the objective operations and heuristic guarantees they require.
- Version 2 runners remain historical; they are not the Version 3 problem API.
- Implementation begins in Sprint V3.1 only after this ADR is accepted.
- No production Monte Carlo, obstacle framework, OMPL, or MoveIt dependency is authorized by this ADR alone.

## Non-goals

- Source-module reorganization to the target tree in the V3 plan.
- API breaks to frozen Version 2 configs or golden fixtures.
- Redefining Version 2 Experiment A or B estimands.
