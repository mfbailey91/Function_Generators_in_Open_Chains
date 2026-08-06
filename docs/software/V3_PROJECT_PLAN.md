# Version 3 Project Plan — Planner-Agnostic Mechanism-Aware Motion Planning

**Status:** proposed architecture and execution plan
**Predecessor:** Version 2 / Experiment A and bounded Experiment B work
**Primary decision:** freeze production scaling while the planning formulation is generalized
**Initial mechanism scope:** certified monotonic transmission branches
**Long-term scope:** noninjective mechanisms, multiple robot DOFs, obstacles, OMPL, and MoveIt

## 1. Why Version 3 exists

Version 2 successfully isolated several mechanism effects and produced reproducible Dijkstra and A* evidence. It also revealed that the experiment architecture had become too tightly coupled to one formulation:

- planar 2R arms;
- a regular output-state lattice;
- four-connected motion primitives in the historical Experiment A graph;
- fixed normalized \(Q\)-space task chords;
- start and goal attachment policies tied to that lattice;
- node expansions as the dominant planner metric;
- one production orchestration model designed around a mechanism-nested task suite.

Those choices were useful for a controlled mechanism probe. They are not a sufficiently general definition of robot motion planning.

Version 3 therefore changes the software center from **a graph experiment** to **a planner-independent motion-planning problem**.

The Monte Carlo work remains trusted evidence for its declared formulation. It is frozen as a historical experiment lineage rather than reinterpreted as a general planner result.

## 2. Scientific objective

Build a framework that can ask, across robot architectures and planner families:

> How does an embedded kinematic transmission change feasibility, path cost, planner effort, selected goal state, and motion quality for the same externally defined robot task?

The physical chain remains

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X,
\]

where:

- \(\mathcal U\) is mechanism or actuator configuration;
- \(g_m\) is the transmission map for mechanism \(m\);
- \(\mathcal Q\) is output-joint configuration;
- \(f\) is robot forward kinematics;
- \(\mathcal X\) is task space.

For the initial monotonic operating-branch study, \(g_m^{-1}\) is unique over the certified range. Later versions may restore noninjective maps and hidden mechanism state.

## 3. Core design rule

The framework must keep the following concepts independent:

1. **physical state** — what uniquely identifies the mechanism and robot;
2. **task** — what the robot is asked to achieve;
3. **planning representation** — coordinates or graph/tree states used by a planner;
4. **local motion** — the continuous motion used to connect nearby states;
5. **validity** — joint, mechanism, collision, and task constraints;
6. **objective** — actuator travel, output travel, Cartesian length, time, energy, or a composite;
7. **planner** — direct, graph, roadmap, tree, batch-informed, or trajectory optimization;
8. **benchmark protocol** — task distribution, classification, repetitions, and statistics.

No experiment runner may define all eight internally.

## 4. Planning problem contract

Conceptually:

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

### 4.1 Physical state

```python
@dataclass(frozen=True)
class PhysicalState:
    u: NDArray[np.float64]
    q: NDArray[np.float64]
    branch_id: str | None = None
    auxiliary_state: Mapping[str, Any] = field(default_factory=dict)
```

For a certified monotonic branch, \(u=g_m^{-1}(q)\) is unique. The explicit \(u\) field remains because objectives, diagnostics, and later noninjective mechanisms require it.

### 4.2 Robot model

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

### 4.3 Goal constraints

Goals are task predicates, not necessarily one configuration:

```python
class GoalConstraint(Protocol):
    def satisfied(self, state: PhysicalState) -> bool: ...
    def residual(self, state: PhysicalState) -> NDArray[np.float64]: ...
    def sample_candidates(self, robot: RobotModel) -> Iterable[PhysicalState]: ...
```

Initial goal types:

- exact output configuration;
- output-joint region;
- planar Cartesian position disk;
- planar pose region \((x,y,\theta)\);
- spatial position sphere;
- orientation tolerance;
- full \(SE(3)\) pose region;
- partial-pose and pointing constraints for 4R and 5R arms.

### 4.4 Planning scene

```python
class PlanningScene(Protocol):
    def state_is_valid(self, state: PhysicalState) -> bool: ...
    def motion_is_valid(self, motion: LocalMotion) -> bool: ...
```

Scene levels are introduced gradually:

1. free space with mechanism and joint limits;
2. static workspace obstacles;
3. self-collision;
4. path constraints and constrained manifolds;
5. dynamic and capability constraints;
6. dynamic environments and replanning.

### 4.5 Local motion

A local motion is continuous:

\[
\gamma:[0,1]\rightarrow\mathcal S.
\]

```python
class LocalMotionModel(Protocol):
    def connect(
        self,
        start: PhysicalState,
        end: PhysicalState,
    ) -> LocalMotion | None: ...
```

Initial connectors:

- output-linear: \(q(t)=(1-t)q_a+tq_b\), with \(u(t)=g_m^{-1}(q(t))\);
- input-linear: \(u(t)=(1-t)u_a+t u_b\), with \(q(t)=g_m(u(t))\);
- Cartesian-linear with IK continuation, later.

Graph adjacency selects candidate neighbors. It does not define the continuous robot motion.

## 5. Mechanism-aware objectives

The initial shared objective is actuator-path length:

\[
J_U[\gamma]
=
\int_0^1
\left\|\frac{d u(t)}{dt}\right\|_2dt.
\]

For a shared output-space local connector,

\[
q(t)=(1-t)q_a+tq_b,
\qquad
u_m(t)=g_m^{-1}(q(t)),
\]

so each mechanism assigns a different cost to the same visible local motion.

Required objective implementations:

- actuator path length;
- output-joint path length;
- Cartesian path length;
- estimated execution time under limits;
- collision or clearance penalties;
- later energy, torque margin, resolution, and terminal capability.

Endpoint Euclidean distance may be used only when a calibration demonstrates that it approximates the integrated local cost at the selected connection scale.

## 6. Task-space planning with configuration-space search

A task may be defined in Cartesian space while search occurs in physical or configuration state.

For the initial 2R position task:

\[
\mathcal G_X
=
\{x:\|x-x_g\|\le\epsilon_X\}.
\]

A state is a goal when

\[
\|f(q)-x_g\|\le\epsilon_X.
\]

On a certified monotonic branch, a common bounded \(Q\)-representation may be shared across mechanisms while actuator costs are induced through

\[
u_m=g_m^{-1}(q).
\]

The initial paired formulation is therefore:

\[
\boxed{
\text{same }Q\text{ geometry}
+
\text{same Cartesian task}
+
\text{mechanism-dependent }U\text{ cost}
}
\]

This comparative formulation is a special case of the general physical-state planning contract, not the universal state model.

## 7. Exact start and goal-region semantics

The start is an exact known physical state. It is never a Cartesian tolerance region.

Roadmap and lattice planners attach the exact start through a temporary query state and validated local connectors. Tree planners use it as the root. A numerical attachment residual may be reported, but it is not task semantics.

The goal tolerance is a real task parameter. It must be identical across paired mechanisms and reported with:

- represented goal-state count;
- IK families represented;
- final Cartesian residual;
- selected goal state;
- direct-connector availability.

Goal tolerance must not be tuned separately for each mechanism to equalize graph-node counts.

## 8. Planner families

### 8.1 Direct reference planners

Implement first:

1. output-linear interpolation;
2. input-linear interpolation;
3. later Cartesian-linear interpolation.

These provide feasibility checks and lower/reference bounds. In free space, an optimizing planner must not report actuator travel below a valid input-linear straight path between the same exact endpoints.

### 8.2 Native deterministic graph planners

Implement transparently:

- breadth-first search for unit-cost diagnostics;
- Dijkstra;
- A*;
- weighted A*;
- bidirectional Dijkstra and A*;
- any-angle or shortcut-capable search.

The first lattice baseline permits simultaneous joint movement. For planar 2R this means an eight-connected stencil, not the historical one-coordinate-at-a-time four-connected stencil.

Connectivity is planner configuration:

```yaml
planner:
  family: lattice
  algorithm: astar
  motion_primitives: q_grid_8_connected
```

It is not part of the robot model.

### 8.3 Native roadmap planners

Implement a small transparent set:

- PRM;
- Lazy PRM;
- PRM*.

Roadmaps test graph search without rectangular-grid orientation and naturally support exact query attachment.

### 8.4 Native tree planners

Implement a small reference set:

- RRT;
- RRTConnect;
- RRT*.

Tree planners test dynamic exploration rather than a preconstructed global graph.

### 8.5 Informed and batch planners

Add after core parity:

- BIT*;
- FMT* or an equivalent batch planner.

These are especially relevant because they combine heuristic guidance, implicit graphs, and optimizing search.

### 8.6 Trajectory optimization and industrial planners

Use external adapters rather than recreating mature stacks initially:

- CHOMP;
- STOMP;
- Pilz PTP/LIN/CIRC;
- later MoveIt Servo as an online/local-control family.

Node expansions are not meaningful for every planner family. Common application metrics and family-specific metrics must coexist.

## 9. OMPL and MoveIt integration

### 9.1 OMPL adapter — algorithm validation

OMPL is the first external backend because it provides mature sampling-based planners while leaving robot semantics to the caller.

The adapter maps:

| V3 framework | OMPL concept |
| --- | --- |
| planning state | `StateSpace` |
| bounds | state-space bounds |
| validity | `StateValidityChecker` |
| local motion | `MotionValidator` |
| goal region | `GoalRegion` / `GoalSampleableRegion` |
| objective | `OptimizationObjective` |
| query | `ProblemDefinition` |
| exploration diagnostics | `PlannerData` |

Initial OMPL planners:

- PRM / PRM*;
- RRTConnect;
- RRT*;
- BIT*;
- one projection-oriented planner such as KPIECE when higher-dimensional studies begin.

The V3 framework remains authoritative for \(U\rightarrow Q\rightarrow X\), tasks, objectives, validity, and benchmark records.

### 9.2 MoveIt adapter — application validation

MoveIt integration comes later and is used for:

- URDF/SRDF-backed robots;
- planning groups;
- self-collision and world collision;
- planning scenes and attached objects;
- pose and path constraints;
- OMPL, Pilz, CHOMP, and STOMP pipelines;
- trajectory processing and application-facing conventions.

The first MoveIt integration is an outbound `MoveItPipelineAdapter` for compatible problems. A mechanism-aware MoveIt planner plugin is a later option.

MoveIt must not become the source of truth for hidden mechanism state or silently replace the mechanism-aware metric with ordinary joint distance.

## 10. DOF and task roadmap

### 10.1 Planar 2R

Task:

\[
(x,y)\in\mathbb R^2.
\]

Purpose:

- validate exact start and Cartesian goal regions;
- compare direct, lattice, roadmap, tree, and OMPL planners;
- understand planner-family sensitivity before obstacles.

### 10.2 Planar 3R

Task:

\[
(x,y,\theta)\in SE(2).
\]

Purpose:

- complete planar pose planning;
- introduce redundant position-only controls;
- exercise multiple IK goal families and orientation tolerances.

### 10.3 Spatial 4R and 5R

Use partial task constraints appropriate to available DOFs:

- position plus tool-axis direction;
- pointing or orientation cone;
- position plus one orientation angle;
- constrained-plane or remote-center tasks.

Do not require an arbitrary six-dimensional pose from an underactuated arm.

### 10.4 Spatial 6R

Task:

\[
G\in SE(3).
\]

Purpose:

- full pose planning;
- URDF and MoveIt application validation;
- self-collision and spatial scenes;
- standard industrial-manipulator comparisons.

## 11. Experiment ladder

### V3-A — Free-space planner semantics

One 2R robot/task corpus, exact starts, Cartesian goal regions, and no collision obstacles.

Compare:

- output-linear;
- input-linear;
- lattice Dijkstra and A*;
- any-angle graph search;
- native PRM and RRTConnect;
- OMPL PRM, RRTConnect, RRT*, and BIT*.

Question:

> Do all planner families see the same feasibility and mechanism ordering, and do optimizing planners approach the direct actuator-space reference?

### V3-B — Representation and local-motion sensitivity

Ablate:

- 4-connected historical lattice;
- 8-connected lattice;
- richer stencil;
- any-angle connections;
- roadmap connections;
- endpoint versus integrated edge cost.

Question:

> Which Version 2 effects were mechanism effects, and which were lattice or local-motion artifacts?

### V3-C — Basic obstacle routing

Only after V3-A and V3-B contracts pass, introduce several frozen scene classes rather than one ad hoc obstacle:

- single blocking obstacle;
- offset obstacle permitting two route families;
- narrow passage;
- obstacle near one IK family;
- scene where direct interpolation remains valid.

Question:

> How does the mechanism-induced metric affect routing when global exploration is genuinely required?

### V3-D — Higher-DOF progression

Run 3R planar pose first, then 4R/5R partial tasks, then 6R full pose.

### V3-E — MoveIt application validation

Reproduce selected mechanism comparisons through standard planning scenes and multiple MoveIt pipelines.

### V3-F — Production populations

Return to Monte Carlo only after task, planner, scene, local-motion, metric, and benchmark contracts are stable.

## 12. Benchmarking contract

### 12.1 Classify before benchmarking

Every task is classified without using the comparative planner outcome:

1. **already satisfied** — start lies in goal region;
2. **direct/local feasible** — a declared direct connector is valid;
3. **global planning required** — direct connectors fail under the scene and constraints;
4. **invalid/unreachable** — task cannot be represented or reached.

Do not pool these regimes into one undifferentiated expansion statistic.

### 12.2 Task-size and difficulty descriptors

Record pre-search descriptors:

- Cartesian start-goal separation;
- direct input-space distance;
- direct output-space distance;
- goal tolerance;
- goal-set measure or represented count;
- IK-family count;
- boundary proximity;
- obstacle or constraint class;
- direct-connector status.

Planner outcome must not be the sole difficulty classifier.

### 12.3 Common application metrics

Every planner returns, where meaningful:

- status and failure taxonomy;
- wall time;
- selected goal state;
- objective cost;
- actuator, output, and Cartesian path length;
- state and motion validity checks;
- collision checks;
- direct-connector availability;
- final task residual;
- reproducibility metadata.

### 12.4 Planner-specific metrics

Examples:

- graph search: expansions, generated, reopened, queue operations, heuristic error;
- roadmap: samples, vertices, attempted/accepted edges, query attachment;
- tree: samples, extension attempts, accepted states, nearest-neighbor operations;
- trajectory optimization: iterations, rollouts, objective evaluations, convergence;
- industrial generators: generation time and constraint compliance.

### 12.5 Paired effect metrics

Retain relative effects such as

\[
\Delta\log N
=
\log\frac{N_F+1}{N_G+1},
\]

but never report them alone. Also report:

\[
\Delta N=N_F-N_G,
\qquad
\Delta t=t_F-t_G,
\qquad
\Delta J=J_F-J_G.
\]

A ten-percent improvement on a trivial search is not equivalent in application importance to a ten-percent improvement on a large search.

Report effects by task class and size/difficulty strata before any overall task-distribution mean.

### 12.6 Diagnostic Q-spanner

Preserve the centered and other designed \(Q\)-space probes as a separate diagnostic suite.

Allowed purpose:

- expose metric orientation;
- inspect local gain effects;
- reveal planner/grid artifacts;
- generate hypotheses for application tasks.

Not allowed:

- present a Q-spanner mean as the representative robot-task effect;
- merge Q-spanner and Cartesian task estimands.

## 13. Result schema

```python
@dataclass
class PlanningResult:
    status: PlanningStatus
    trajectory: Trajectory | None
    selected_goal_state: PhysicalState | None

    wall_time_s: float
    objective_cost: float | None
    path_length_u: float | None
    path_length_q: float | None
    path_length_x: float | None

    state_validity_checks: int | None
    motion_validity_checks: int | None
    collision_checks: int | None

    task_class: str
    final_goal_residual: float | None
    planner_metrics: Mapping[str, JSONScalar]
    provenance: ResultProvenance
```

The schema must support deterministic and stochastic planners without pretending that all have node expansions.

## 14. Target source architecture

```text
src/inequality_mechanisms/
├── core/
│   ├── state.py
│   ├── robot.py
│   ├── scene.py
│   ├── goals.py
│   ├── constraints.py
│   ├── local_motion.py
│   ├── objectives.py
│   ├── planner.py
│   └── results.py
├── mechanisms/
│   ├── gearbox.py
│   ├── fourbar.py
│   ├── operating_branch.py
│   └── legacy_full_cycle.py
├── robots/
│   ├── planar_serial.py
│   ├── spatial_serial.py
│   └── urdf_adapter.py
├── planners/
│   ├── direct/
│   ├── lattice/
│   ├── roadmap/
│   ├── tree/
│   └── batch/
├── adapters/
│   ├── ompl/
│   └── moveit/
├── scenes/
│   ├── free_space.py
│   ├── planar_obstacles.py
│   └── spatial_scene.py
├── benchmarks/
│   ├── tasks.py
│   ├── classification.py
│   ├── metrics.py
│   ├── statistics.py
│   └── reports.py
├── experiments/
│   ├── legacy_v2/
│   └── v3/
└── visualization/
```

Stable V2 modules should not be moved merely to match this tree. Introduce adapters and migrate only when a move adds architectural value.

## 15. Migration strategy

Use a strangler migration rather than a repository-wide rewrite.

1. Freeze and tag the trusted V2 evidence revision.
2. Preserve V2 configs, runners, reports, and schemas as historical experiments.
3. Add the V3 core beside existing modules.
4. Wrap the certified V2 mechanism branches as V3 `RobotModel` components.
5. Wrap existing Dijkstra and A* as V3 planner adapters before rewriting them.
6. Reproduce one known V2 case through V3 to prove compatibility.
7. Build the new free-space Cartesian vertical slice.
8. Add new planner families through the common interface.
9. Add OMPL before MoveIt.
10. Return to production campaigns only after V3 benchmark gates pass.

No V2 result is silently recomputed or reinterpreted under V3.

## 16. Milestone roadmap

### V3-M0 — Architecture contract and evidence freeze

- accept the V3 plan;
- freeze V2 production scaling;
- inventory reusable V2 modules;
- define planner-independent interfaces;
- define benchmark classification and metric contracts;
- assign ADR numbers after synchronizing the global ADR index.

### V3-M1 — Core problem and result model

- implement physical state, robot, goal, scene, local-motion, objective, planner, and result interfaces;
- add serialization and configuration discriminators;
- add compatibility adapters for existing mechanisms and search.

### V3-M2 — Direct 2R vertical slice

- planar 2R robot;
- exact start;
- Cartesian position goal region;
- output-linear and input-linear planners;
- task classification;
- common result schema.

### V3-M3 — Lattice and local-motion validation

- eight-connected simultaneous-joint lattice;
- exact start overlay;
- integrated actuator edge cost;
- Dijkstra, A*, weighted A*, and any-angle reference;
- four/eight/richer connectivity ablation.

### V3-M4 — Native roadmap and tree planners

- PRM, Lazy PRM, PRM*;
- RRT, RRTConnect, RRT*;
- common stochastic seed and repetition protocol.

### V3-M5 — OMPL adapter

- custom state space;
- mechanism-aware objective;
- goal region;
- state and motion validity;
- planner-data extraction;
- parity runs with native planners.

### V3-M6 — Free-space planner evidence

- frozen external Cartesian bank;
- direct/local/global classification;
- task-size strata;
- common and family-specific metrics;
- no population inference until representation sensitivity is understood.

### V3-M7 — Scene and obstacle framework

- planar collision geometry;
- frozen scene classes;
- motion validation and collision instrumentation;
- routing studies across planner families.

### V3-M8 — 3R planar pose

- full \(SE(2)\) goal regions;
- redundant position-only controls;
- orientation-aware metrics and heuristics.

### V3-M9 — 4R/5R partial tasks

- pointing, orientation cones, constrained-plane, and partial-pose goals.

### V3-M10 — 6R and MoveIt application adapter

- URDF/SRDF robot models;
- spatial collision scenes;
- full \(SE(3)\) pose goals;
- OMPL, Pilz, CHOMP, and STOMP pipeline comparisons.

### V3-M11 — Production mechanism populations

- freeze task, scene, planner, and mechanism banks;
- planner-appropriate statistical designs;
- hardware and runtime calibration;
- immutable evidence packages.

## 17. Hard gates

| Gate | Blocks |
| --- | --- |
| V2 evidence revision frozen and reproducible | V3 compatibility claims |
| Core interfaces accepted | implementation beyond adapters |
| Exact start and goal-region contracts pass | planner comparisons |
| Direct planners establish reference costs | optimizing-planner interpretation |
| Local-motion and edge-cost integration converge | graph/roadmap comparison |
| 8-connected and richer-connectivity effects understood | lattice production claims |
| Common result schema works across deterministic and stochastic planners | OMPL promotion |
| Native/OMPL parity is understood | obstacle studies |
| Task classification and benchmark strata accepted | aggregate performance claims |
| Free-space semantics stable | obstacle routing |
| 2R planner-family evidence reviewed | 3R implementation |
| 3R task semantics stable | 4R–6R progression |
| MoveIt adapter preserves mechanism-aware semantics | application-facing claims |
| Planner-specific statistics accepted | any production Monte Carlo campaign |

## 18. Initial acceptance criteria

Version 3 may begin broader planner experiments only when:

1. the same `PlanningProblem` is solved without experiment-specific branches by direct, lattice, roadmap, and tree planners;
2. exact starts are preserved, not represented by a start tolerance;
3. Cartesian goal tolerance is fixed and reported consistently;
4. output-linear paths are identical in \(Q\) and \(X\) across paired mechanisms;
5. input-linear reference paths are valid and no optimizing planner beats their Euclidean actuator lower bound for identical endpoints;
6. A* and Dijkstra agree on optimal cost for the same graph and objective;
7. stochastic planners reproduce under frozen seeds and repetition contracts;
8. task classification precedes performance aggregation;
9. relative log effects are accompanied by absolute compute and cost effects;
10. Q-spanner diagnostics remain separate from application-task estimands.

## 19. Immediate next action

Do not start with obstacle implementation or a new population campaign.

Begin with Sprint V3.0:

- freeze the V2 evidence lineage;
- inventory the current code and call sites;
- accept the V3 interfaces and benchmark contract;
- define adapter boundaries;
- produce a migration map and golden compatibility test plan.

## 20. External planner documentation

These references define integration capabilities, not the V3 scientific contract:

- [OMPL geometric planner catalog](https://ompl.kavrakilab.org/namespaceompl_1_1geometric.html)
- [OMPL planner base and PlannerData](https://ompl.kavrakilab.org/classompl_1_1base_1_1Planner.html)
- [MoveIt motion-planning concepts](https://moveit.picknik.ai/main/doc/concepts/motion_planning.html)
- [MoveIt OMPL interface](https://moveit.picknik.ai/main/doc/examples/ompl_interface/ompl_interface_tutorial.html)
- [MoveIt constrained OMPL planning](https://moveit.picknik.ai/main/doc/how_to_guides/using_ompl_constrained_planning/ompl_constrained_planning.html)
- [Pilz industrial motion planner](https://moveit.picknik.ai/main/doc/how_to_guides/pilz_industrial_motion_planner/pilz_industrial_motion_planner.html)
- [CHOMP planner](https://moveit.picknik.ai/main/doc/how_to_guides/chomp_planner/chomp_planner_tutorial.html)
- [STOMP planner](https://moveit.picknik.ai/main/doc/how_to_guides/stomp_planner/stomp_planner.html)
