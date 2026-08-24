# ADR-031 — OMPL Planner Geometry Must Be Explicit

**Status:** Accepted; implemented by completed Sprint V4.2C
**Applies to:** Version 3 OMPL adapter; Version 4 Column A planning diagnostics
**Related:** ADR-021, ADR-022, ADR-023, ADR-024, ADR-025, ADR-026, ADR-029, ADR-030
**Supersedes:** nothing; does not close `V3-DEFER-001`

## Context

The first OMPL adapter was deliberately narrow. It established parity with native PRM and RRTConnect while keeping the project authoritative for physical state, \(U\rightarrow Q\rightarrow X\), exact starts, finite goal realization, local motion, validity, actuator-travel cost, and result classification.

That adapter currently plans in a bounded Euclidean actuator state space. Its nearest-neighbor distance and path-length objective are both Euclidean in U. This is correct for the certified input-linear actuator-travel problem, but the planner name alone no longer describes where the nonlinear transmission enters an experiment.

Different OMPL planners consume geometry through different algorithmic channels:

- state sampling;
- state-space distance and nearest-neighbor queries;
- local interpolation and motion validation;
- optimization objective and cost-to-go estimates;
- finite goal representation;
- low-dimensional exploration projections;
- batch, tree, or roadmap construction.

Without an explicit declaration, a comparison labeled only “BIT* versus RRT*” can silently mix different state coordinates, samplers, projections, objectives, goal realizations, or budgets. It can also tempt a report to treat unrelated family-specific events as one common search-effort metric.

## Decision

### 1. U remains authoritative physical state

For the present certified monotonic mechanism program, OMPL state coordinates remain actuator coordinates:

\[
\text{OMPL state}=u.
\]

Every OMPL state is reconstructed into the authoritative `PhysicalState` through the project robot model. Mounted Q and Cartesian X are derived physical projections. They may define tasks, metrics, reports, or exploration projections, but they do not replace physical state identity.

A future noninjective/full-cycle extension must continue to preserve assembly and hidden mechanism state rather than collapsing physical states that share Q or X.

### 2. The primary objective remains Euclidean actuator travel

Under `InputLinearMotion` and `ActuatorTravelObjective`, OMPL path length is an exact adapter for:

\[
J_U(\gamma)=\int\|\dot u\|_2\,dt.
\]

Primary V4.2C rows use the existing bounded `RealVectorStateSpace` and Euclidean raw-U distance. A diagnostic that changes state distance, sampling measure, objective, or local motion must receive a distinct experiment identity and may not be pooled with the primary portfolio.

### 3. Every planner row declares its geometry

Every OMPL result must serialize:

```text
planner_role
state_coordinates
sampling_measure
nearest_neighbor_distance
optimization_objective
cost_to_go_heuristic
exploration_projection
projection_normalization
projection_cell_sizes
goal_representation
local_motion_model
```

These fields form one common planner-geometry record. Planner-specific parameters remain namespaced but cannot substitute for the common declaration.

### 4. The finite physical goal set is shared

Primary planner comparisons receive:

- the same exact physical start;
- the same physical task predicate;
- the same frozen finite represented goal candidates;
- the same candidate IDs and ordering;
- the same goal-generator provenance.

If an OMPL planner or Python binding cannot safely consume the finite multi-goal representation, the limitation is typed. A sequential single-goal envelope may be retained as an explicitly different adapter condition; it is not described as a true multi-goal solve.

### 5. Projection-guided planners change projection only

For KPIECE projection diagnostics:

\[
\pi_U(u),\qquad \pi_Q(u)=g_m(u),\qquad \pi_X(u)=f(g_m(u))
\]

are normalized using frozen, pre-outcome bounds and explicit cell sizes. The OMPL state, local motion, objective, task, seed, budget, and all nonprojection planner parameters remain unchanged.

Mounted robot joint coordinates from ADR-029 are mandatory for \(\pi_Q\). Native follower angles are diagnostic provenance only.

### 6. Sampling claims are explicit

The primary sampling measure is uniform in raw U. Process-isolated seeding does not by itself prove that two mechanisms receive identical sample sequences. A paired precomputed or normalized-fraction sampler may be used only when the installed Python binding supports it safely and the sampler identity and digest are recorded.

Unsupported binding features fail closed or remain typed optional omissions. They are not approximated by undocumented planner modifications.

### 7. Planner-family metrics remain namespaced

Common physical outcomes include success, selected goal, objective cost, reference gap, path lengths, residuals, timing, and validity checks.

Family-specific work metrics remain separate:

- graph expansions and queue events;
- roadmap samples, vertices, and edges;
- tree vertices, rewires, and nearest-neighbor operations;
- BIT* batches and queue properties;
- FMT sample counts and wavefront structure;
- KPIECE projection cells;
- optimization checkpoints.

No report may aggregate these into one cross-family “search effort” count or a universal winner score.

### 8. Free-space interpretation is bounded

The certified free-space actuator box and direct U-linear connector provide a strong reference but a weak routing challenge. V4.2C is therefore a planner-semantics, convergence, and projection-sensitivity diagnostic. It does not establish obstacle-routing superiority or general application performance.

Valid direct connections may not be disabled to manufacture nonlocal behavior.

### 9. Required and optional planners are separated

Required V4.2C additions:

- OMPL RRT*;
- OMPL BIT*;
- OMPL FMT;
- geometric KPIECE with normalized U, Q, and X projections.

Retained controls:

- direct U/Q controls;
- lattice Dijkstra/A*;
- OMPL PRM/RRTConnect.

Optional, nonblocking control:

- geometric PDST after capability and required-portfolio gates.

Additional informed, task-space, transition-based, trajectory-optimization, dynamics, and native planner implementations remain deferred.

### 10. Documentation does not authorize implementation

Landing ADR-031 and the V4.2C sprint plan did not, by itself, change
`ACTIVE_SPRINT.md`. Implementation started only after a separate change
authorized V4-230–V4-239. Sprint V4.2C later implemented this decision and
returned authorization to none without activating V4.3. This ADR does not
supersede ADR-030 (paired final topology and nonfinite edge semantics).

## Consequences

### Benefits

- Planner comparisons state exactly where the mechanism map enters the algorithm.
- KPIECE can test U/Q/X exploration views without changing physical state.
- Optimizing planner convergence can be compared with the direct represented-set reference.
- Existing PRM/RRTConnect evidence retains its proper architecture-control role.
- Result records remain interpretable when planner families expose different internal events.
- Python-binding limitations become evidence rather than hidden implementation drift.

### Costs

- The adapter requires a shared session/refactor before adding wrappers.
- Projection bounds, cell sizes, parameter normalization, and budgets must be calibrated and frozen.
- Stochastic runs require process isolation and larger retained provenance.
- Some desirable OMPL C++ features may be unavailable or awkward in Python and must remain typed omissions.
- The report must be organized by scientific question rather than a simple planner leaderboard.

## Implementation consequences

Sprint V4.2C must add:

- a planner-geometry record;
- an OMPL Python-binding capability matrix;
- thin RRT*/BIT*/FMT/KPIECE wrappers;
- explicit normalized U/Q/X projection evaluators;
- process-isolated staged runners;
- checkpoint and family-specific metrics;
- a fresh guarded evidence package.

Existing V3 OMPL behavior must remain regression-tested. V4.2C does not modify frozen evidence, mechanism certificates, mounted-coordinate rules, V4.3 wrench mathematics, or the deferred native-planner backlog.

## Test consequences

Required tests include:

- optional-dependency behavior;
- exact-start and finite-goal parity;
- objective/path-cost agreement;
- mounted-Q projection correctness;
- U/Q/X ablation factor isolation;
- process-isolated seed provenance;
- planner parameter and binding capability recording;
- namespaced metrics;
- immutable predecessor artifact digests;
- report nonclaim and link-integrity checks.

## Rejected alternatives

### Replace U with Q as the OMPL state

Rejected because it changes physical identity and does not generalize to noninjective transmissions.

### Give every planner a mechanism-specific custom distance immediately

Rejected for the primary portfolio because it would mix planner family with a changed metric/objective contract. Such a study requires a separate diagnostic identity.

### Add every informed OMPL planner at once

Rejected because ABIT*, AIT*, EIT*, Informed RRT*, and related planners add overlapping machinery before the simpler RRT*/BIT*/FMT/KPIECE distinctions are understood.

### Disable direct connections in free space

Rejected because it creates an artificial planning problem and invalidates the direct-reference interpretation.

### Treat PDST as fully metric independent

Rejected. PDST avoids RRT*-style nearest-neighbor rewiring but still depends on a projection, range, sampling, and finite-time behavior.

### Close the native planner backlog through OMPL wrappers

Rejected. External-library coverage and project-owned native implementations answer different software and scientific questions.
