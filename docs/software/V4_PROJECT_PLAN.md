# Version 4 Project Plan — Kinematic Transmission Geometry in Planar 2R

- **Status:** V4.0 geometry kernel closed; no source-code authorization until `ACTIVE_SPRINT.md` explicitly activates a later sprint
- **Predecessor:** Version 3 planner-independent physical-state and motion-planning contracts
- **Immediate dependency:** formal Version 3.6C gate disposition and a separate active-sprint transition
- **Initial robot:** planar 2R open chain
- **Initial mechanisms:** certified monotonic four-bar pair and span-matched affine gearbox pair
- **Fresh artifact root:** `results/v4_review/`

## 1. Why Version 4 exists

Version 3 corrected the project’s software center. It moved from one graph experiment to a planner-independent physical planning problem and established common state, task, local-motion, objective, planner, and result contracts.

The emerging theory is broader than motion planning. The same physical transmission map

\[
\mathcal U\xrightarrow{g_m}\mathcal Q\xrightarrow{f}\mathcal X
\]

also governs:

- instantaneous velocity;
- inverse differential kinematics;
- force and wrench pullback;
- actuator-travel metrics;
- potential gradients and continuous flows;
- local resolution and directional capability.

Version 4 therefore changes the immediate research question from

> How does the transmission reshape a planner?

into

> How does the same kinematic transmission reshape the fundamental geometric objects consumed by planning, velocity generation, force transmission, and continuous motion policies, and when do those changes matter for an application?

Version 4 does not discard the Version 3 roadmap. It builds on the V3 core and temporarily keeps the research platform at planar 2R so that the effect columns can be isolated before dimensionality, collision, dynamics, or hardware add new confounds.

## 2. Formal object and method

The formal physical object is the **kinematic transmission**. Its map is

\[
\mathbf q=g_m(\mathbf u).
\]

The mechanism acts as a **function generator** by producing that input-output relationship.

The method is **kinematic transmission geometry**: use the same map consistently on

- configurations;
- tangent vectors;
- covectors;
- metrics;
- measures;
- rank and singularity structure.

This preserves the existing open-chain formulation rather than replacing it.

## 3. Scientific scope

### 3.1 Included initially

- planar 2R kinematics with analytic \(f(q)\) and \(J_f(q)\);
- one canonical certified monotonic four-bar pair;
- one span-matched affine gearbox pair;
- common bounded \(Q\) domain;
- exact physical states carrying both \(u\) and \(q\);
- dense shared-\(Q\) intrinsic atlases;
- paired application task banks;
- deterministic controls before stochastic populations;
- fresh, versioned HTML/JSON result packages.

### 3.2 Explicitly excluded from the first program

- full-cycle or noninjective mechanisms;
- collision geometry and obstacles;
- rigid-body dynamics and inertia;
- friction, backlash, compliance, and transmission losses;
- electrical actuator models;
- 3R redundancy claims;
- spatial wrench claims;
- MoveIt integration;
- biological equivalence claims;
- mechanism optimization before the estimands are stable.

## 4. Shared differential geometry

At each certified physical state,

\[
J_g=\frac{\partial q}{\partial u},
\qquad
J_f=\frac{\partial x}{\partial q},
\qquad
J_{xu}=J_fJ_g.
\]

### 4.1 Tangent pushforward

\[
\dot q=J_g\dot u,
\qquad
\dot x=J_{xu}\dot u.
\]

### 4.2 Covector pullback

\[
\tau_u=J_g^\mathsf T\tau_q,
\qquad
\tau_u=J_{xu}^\mathsf TF.
\]

### 4.3 Actuator metric expressed on Q

For \(W_u\succ0\),

\[
M_Q^{(U)}
=
J_g^{-\mathsf T}W_uJ_g^{-1}.
\]

### 4.4 Mobility expressed on Q

\[
B_Q^{(U)}
=
J_gW_u^{-1}J_g^\mathsf T.
\]

### 4.5 Task-space velocity Gramian

\[
B_X^{(U)}
=
J_{xu}W_u^{-1}J_{xu}^\mathsf T.
\]

The Version 4 geometry core owns these quantities and their rank semantics. Column-specific code may not rederive alternate versions silently.

## 5. Four fundamental effect columns

## 5.1 Column A — global planning and cost-to-go

### Intrinsic object

- physical state topology;
- actuator metric and geodesic distance;
- discrete or continuous cost-to-go;
- goal preimages and selected terminal state.

### Existing foundation

Version 3 already supplies direct, lattice, roadmap, tree, and OMPL planning contracts. Version 4 consumes those results rather than rebuilding the planning stack.

### Application questions

- Does a common work region become mechanically near or far?
- Does the mechanism favor one acceptable terminal state?
- Does planner effort change after graph and task confounds are controlled?
- Does lower actuator cost trade against Cartesian path quality or terminal capability?

### Common metrics

- feasibility and task class;
- actuator, output, and Cartesian path length;
- selected goal state;
- objective suboptimality;
- planner-family effort metrics;
- task residual;
- terminal velocity/wrench/flow descriptors from the other columns.

## 5.2 Column B — inverse instantaneous kinematics and velocity capability

### Intrinsic object

\[
\dot x=J_{xu}\dot u.
\]

With actuator-rate limits \(\dot u\in\mathcal V_u\),

\[
\mathcal V_x(q)=J_{xu}(q)\mathcal V_u.
\]

### Initial 2R application questions

- How much actuator rate is required for a unit Cartesian direction?
- Which Cartesian directions saturate first?
- How do damping and singular-value thresholds change tracking error?
- Does the transmission move or intensify composite singularity regions?

### Important 2R limitation

The 2R Cartesian-position task is square and generally nonredundant. It can validate conditioning, rate demand, saturation, and damped inversion. It cannot establish transmission-dependent null-space posture selection. That question remains a later 3R extension.

### Metrics

- singular values and condition numbers of \(J_g\), \(J_f\), and \(J_{xu}\);
- feasible Cartesian velocity polygon or ellipse;
- directional maximum speed;
- actuator-rate norm;
- rate-limit utilization and saturation count;
- damped least-squares residual;
- tracking RMS and peak error;
- command continuity.

## 5.3 Column C — static wrench capability

### Intrinsic object

\[
\tau_u=J_{xu}^\mathsf TF.
\]

Given actuator effort box \(\mathcal T_u\),

\[
\mathcal W_x(q)
=
\{F:J_{xu}^\mathsf TF\in\mathcal T_u\}.
\]

### Initial 2R application questions

- Where can the robot push or hold most strongly in selected directions?
- Does a low transmission-gain region create useful terminal force margin?
- Which capability losses originate in the transmission versus open-chain geometry?
- Does a planning-favorable terminal state have adequate wrench margin?

### Metrics

- exact planar wrench polygon;
- directional force margin;
- polygon area;
- anisotropy;
- actuator utilization;
- worst-case and application-weighted wrench margin;
- rank attribution for \(J_g\), \(J_f\), and \(J_{xu}\).

## 5.4 Column D — potential fields and continuous flow

### Intrinsic object

For \(\Phi_Q(q)\), Euclidean actuator-space descent produces

\[
\dot q
=-B_Q^{(U)}\nabla_q\Phi_Q.
\]

For \(\Phi_X(x)\),

\[
\dot x
=-B_X^{(U)}\nabla_x\Phi_X.
\]

### Required controls

1. Euclidean descent defined directly in \(Q\);
2. Euclidean descent in \(U\) through the physical transmission;
3. covariant descent that cancels regular coordinate reparameterization;
4. later singular/limit cases reported separately.

### Application questions

- Does the mechanism create fast transit followed by slow terminal capture?
- How does actuator travel trade against convergence time?
- Does an obstacle-avoidance field acquire different basins or stalls?
- Which differences survive the covariant coordinate control?

### Metrics

- success and stall classification;
- convergence time or integration steps;
- actuator/output/Cartesian path length;
- peak actuator speed and acceleration;
- terminal error;
- minimum clearance when obstacles are later introduced;
- basin volume;
- critical-point and rank attribution.

## 6. Common evidence ladder

Every column must follow the same sequence:

\[
\boxed{
\text{intrinsic atlas}
\rightarrow
\text{application task distribution}
\rightarrow
\text{solver/controller}
\rightarrow
\text{paired outcome metrics}
}
\]

### 6.1 Intrinsic atlas

Describe what the transmission does without judging it:

- maps \(u\leftrightarrow q\);
- \(J_g\), \(J_f\), and \(J_{xu}\);
- metrics and mobility;
- velocity and wrench sets;
- flow vectors;
- rank and singularity fields.

### 6.2 Application distribution

A task sample may contain

\[
\xi=(q_s,x_g,\dot x_d,F_d,\Phi,\mathcal O),
\]

with only the relevant fields populated for a given column.

Two corpora are required:

1. a neutral, approximately uniform control corpus;
2. an application-weighted corpus that encodes a declared work region and preferred motion/force directions.

### 6.3 Solver or controller

Use one declared family at a time:

- planning solver;
- inverse differential solver;
- exact polytope or directional optimization;
- ODE-integrated flow controller.

### 6.4 Paired outcomes

The gearbox and four-bar receive the same external task and shared \(Q/X\) representation. Each retains its own physical \(u\) state and actuator-side effort.

No pooled result may hide mechanism-specific infeasibility, direct-feasibility asymmetry, rank loss, or saturation.

## 7. Comparison and fairness contract

### 7.1 Shared physical output domain

The canonical mechanism pair must share:

- the same bounded output ranges;
- the same planar link geometry;
- the same sampled \(Q\) states;
- the same Cartesian poses;
- the same task bank and ordering.

### 7.2 Equivalent gearbox control

The affine gearbox comparison must declare the matching policy. The initial control uses the accepted span/equivalent-gain convention and records the resulting ratio per axis.

### 7.3 Same actuator units and weights

Actuator velocity and effort limits must be stated in actuator-side units. Any weight matrix \(W_u\) must be serialized and held common across the mechanism pair unless the experiment explicitly studies actuator sizing.

### 7.4 Rank and regularization provenance

Every inverse, metric, or solver result records:

- rank tolerance;
- singular values;
- full-rank status;
- damping or regularization policy;
- saturation policy;
- failure reason.

### 7.5 No universal “better mechanism” score

A mechanism may improve one column while degrading another. Scalar aggregation is allowed only when application weights and normalization references are declared before comparative outcomes are inspected.

## 8. Target software architecture

Version 4 adds focused packages without reorganizing the existing repository wholesale.

```text
src/inequality_mechanisms/
├── transmission_geometry/
│   ├── __init__.py
│   ├── errors.py
│   ├── protocols.py
│   ├── differential.py
│   ├── metrics.py
│   └── snapshot.py
├── differential_ik/
│   ├── solvers.py
│   ├── limits.py
│   └── results.py
├── capabilities/
│   ├── velocity.py
│   └── wrench.py
├── flows/
│   ├── potentials.py
│   ├── policies.py
│   ├── integrators.py
│   └── results.py
├── experiments/
│   └── v4/
└── visualization/
    └── v4/
```

Only the first package is authorized by Sprint V4.0 when that sprint is activated. Later directories are target boundaries, not permission to implement ahead.

## 9. Common record families

### 9.1 Geometry snapshot

```python
@dataclass(frozen=True, slots=True)
class KinematicGeometrySnapshot:
    state: PhysicalState
    x: NDArray[np.float64]
    j_u_to_q: NDArray[np.float64]
    j_q_to_x: NDArray[np.float64]
    j_u_to_x: NDArray[np.float64]
    rank_u_to_q: RankReport
    rank_q_to_x: RankReport
    rank_u_to_x: RankReport
    actuator_weight: NDArray[np.float64]
    actuator_metric_on_q: NDArray[np.float64] | None
    mobility_on_q: NDArray[np.float64]
    mobility_on_x: NDArray[np.float64]
    provenance: Mapping[str, Any]
```

### 9.2 Column result

Each column returns a typed result containing:

- status and failure taxonomy;
- input task;
- selected physical state or trajectory;
- common geometry snapshot references;
- column-specific metrics;
- numerical policy;
- provenance.

### 9.3 Trial envelope

Cross-column reports join records by stable identifiers:

- `mechanism_pair_id`;
- `mechanism_id`;
- `task_id`;
- `q_sample_id` or `trajectory_id`;
- `column_id`;
- `solver_id`;
- `config_digest`;
- `code_revision`.

## 10. Version 4 sprint roadmap

| Sprint | Purpose | Primary question |
| --- | --- | --- |
| **V4.0** | Kinematic geometry core | Can every column consume one verified \(J_g/J_f/J_{xu}\), metric, mobility, and duality implementation? |
| **V4.1** | Planar-2R intrinsic geometry atlas | What fields does the canonical gearbox/four-bar pair induce over the same \(Q/X\) domain? |
| **V4.2** | Inverse instantaneous kinematics and velocity capability | How does the transmission change actuator-rate demand, conditioning, saturation, and trackable Cartesian velocity? |
| **V4.3** | Static wrench capability | How does the transmission change exact planar wrench sets and terminal directional force margin? |
| **V4.4** | Potential fields and continuous flow | How does the transmission precondition descent, convergence, basins, and actuator travel under coordinate controls? |
| **V4.5** | Application task corpus and integrated 2R report | Do the four columns tell a coherent application-conditioned story on one frozen task bank? |
| **V4.6** | Paired mechanism population and Monte Carlo | Which transmission descriptors predict column-specific effects across a controlled mechanism population? |
| **V4.7** | Cross-column trade space and paper-ready closeout | Which benefits are robust, which are tradeoffs, and which claims are justified before increasing DOF? |

Trajectory optimization is a later synthesis layer. It is not required to establish the first four columns.

## 11. Sprint gates

### Gate V4-A — shared mathematics

V4.0 must close before any velocity, wrench, or flow implementation begins.

### Gate V4-B — deterministic canonical pair

V4.1–V4.4 must each pass analytic/control tests on one frozen gearbox/four-bar pair before any population study.

### Gate V4-C — application contract

V4.5 freezes the neutral and application-weighted task banks before V4.6 Monte Carlo.

### Gate V4-D — inference

V4.6 must predeclare estimands, exclusions, paired statistics, and confirmation policy before production execution.

### Gate V4-E — dimensional decision

V4.7 decides which questions require 3R redundancy, spatial 6R, obstacles, dynamics, or hardware. It does not assume every column must immediately scale in the same way.

## 12. Artifact policy

Fresh Version 4 outputs use only:

```text
results/v4_review/
├── v4_0_kinematic_geometry_core/
├── v4_1_planar2r_geometry_atlas/
├── v4_2_differential_ik_velocity/
├── v4_3_static_wrench/
├── v4_4_potential_flow/
├── v4_5_application_integrated/
├── v4_6_population/
└── v4_7_closeout/
```

Version 1–3 result packages are immutable provenance. Version 4 readers may import historical data but may not rewrite historical records into a new schema in place.

Every generated package includes:

- `manifest.json`;
- resolved configuration;
- code revision;
- environment record;
- trial-level machine-readable data;
- exclusions and failures;
- a human-readable `index.html`;
- figure-generation provenance;
- schema version.

## 13. Testing strategy

### 13.1 Analytic controls

- identity gearbox;
- fixed diagonal gearbox;
- Planar2R analytic Jacobian;
- quadratic potentials;
- axis-aligned actuator velocity and effort boxes.

### 13.2 Numerical controls

- finite differences of \(g\), \(f\), and \(f\circ g\);
- virtual-power equality;
- metric–mobility inverse identity on regular states;
- gradient pullback finite differences;
- exact polygon vertex checks.

### 13.3 Regression controls

- V3.6C audit metric values on fresh regular samples;
- unchanged V3 schemas and frozen artifact digests;
- deterministic task and atlas generation.

### 13.4 Scientific controls

- affine gearbox/null control;
- shared \(Q\) and shared \(X\) representations;
- coordinate-covariant flow control;
- neutral versus application-weighted task distributions;
- rank/saturation strata reported separately.

## 14. Relationship to the current active program

Applying the Version 4 planning patch does not change the active sprint.

Before source implementation:

1. review the completed V3.6C artifact;
2. record the V3.6C gate disposition;
3. update `ACTIVE_SPRINT.md` in a separate explicit change;
4. authorize only V4-000–V4-009;
5. leave V3.7 and later work held unless separately reactivated.

The planned Version 3 dimensional roadmap remains documented. Version 4 reorders the immediate research focus; it does not erase the 3R/6R work.

## 15. Version 4 exit claim

If V4.0–V4.7 close successfully, the project may claim:

> On a controlled planar 2R open chain, a kinematic transmission has been treated as a common geometric layer whose effects were measured consistently in global planning, instantaneous velocity generation, static wrench capability, and continuous potential flow. Deterministic controls and paired mechanism populations identify both application-specific benefits and cross-column tradeoffs without treating one solver representation as the theory itself.

It may not yet claim:

- generality to redundant or spatial manipulators;
- dynamic or energetic superiority;
- collision-routing superiority;
- biological equivalence;
- universal reduction in planning or control complexity.
