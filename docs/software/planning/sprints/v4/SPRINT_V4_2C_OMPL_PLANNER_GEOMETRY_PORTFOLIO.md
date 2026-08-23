# Sprint V4.2C — OMPL Planner-Geometry Portfolio and Projection Diagnostics

- **Status:** drafted / blocked; V4-230–V4-239 reserved; unauthorized until Sprint V4.2B closes, `ACTIVE_SPRINT.md` returns to no authorization, and a separate activation change explicitly names this range
- **Depends on:** corrected V4.2B mounted-coordinate planning bank and case realization; closed V3.5 OMPL adapter; accepted ADR-023 through ADR-026; accepted ADR-029; accepted ADR-030 (paired topology); accepted ADR-031
- **Independent sibling:** V4.3 intrinsic static wrench may be activated separately after V4.2B; V4.2C does not alter the wrench mathematics or its artifact lineage
- **Blocks:** any V4.6 integrated-report claim that the planning column has been tested across mechanism-sensitive sampling, optimization, and projection-guided planner families
- **Reserved work packages:** V4-230–V4-239
- **Does not reuse:** V4-220–V4-229 or V4-300–V4-309
- **Artifact target:** `results/v4_review/v4_2c_ompl_planner_portfolio/`
- **Architecture decision:** `docs/software/architecture/adr/ADR-031-ompl-planner-geometry-contract.md`
- **Implementation guide:** `docs/software/planning/sprints/v4/V4_2C_CURSOR_IMPLEMENTATION_GUIDE.md`
- **Planning-only landing rule:** the documentation patch that introduces this sprint must not edit `ACTIVE_SPRINT.md`, `src/`, `tests/`, `configs/`, or `results/`

## 1. Sprint purpose

Expand the existing OMPL adapter from its initial PRM/RRTConnect parity slice into a bounded planner portfolio selected specifically to expose how the nonlinear transmission map

\[
\mathcal U\xrightarrow{g_m}\mathcal Q\xrightarrow{f}\mathcal X
\]

enters sampling, nearest-neighbor geometry, optimization, heuristic ordering, and exploration projections.

The current OMPL implementation is intentionally narrow: it plans in a bounded Euclidean `RealVectorStateSpace` over actuator coordinates, uses input-linear local motion, maps actuator travel to OMPL path length, realizes a finite physical goal set, and exposes only PRM and RRTConnect. V4.2C preserves that authoritative physical contract while adding planners whose internal geometry is more informative for this project.

This sprint is a **planner-semantics and mechanism-sensitivity diagnostic**. It is not an obstacle-routing study, a production mechanism-population campaign, or a universal planner ranking.

## 2. Sprint question

> When every planner receives the same exact physical start, the same frozen represented goal set, the same actuator-space local motion, and the same actuator-travel objective, which effects of the nonlinear \(U\rightarrow Q\rightarrow X\) map appear in optimizing trees, implicit sampled graphs, fixed-sample cost wavefronts, and projection-guided exploration?

The subsidiary questions are:

1. Do RRT*, BIT*, and FMT approach the direct represented-set actuator-travel reference consistently across the paired mechanisms?
2. Does the selected terminal goal candidate change with planner family or only with finite-time suboptimality?
3. Does KPIECE exploration change when the same physical U-state is viewed through normalized U, Q, or X projections?
4. Which observed differences are attributable to the planner's sampling or exploration geometry rather than to the physical task, objective, or local-motion contract?
5. Do the existing PRM and RRTConnect results remain useful as architecture controls without being promoted to primary mechanism evidence?

## 3. Interpretation boundary: why free space still matters

For the certified monotonic planar-2R branch, the physical actuator domain is a bounded box, the declared local motion is input-linear, and the objective is Euclidean actuator travel. When the direct connector to a represented goal is valid, the direct U-linear path is the reference path for that fixed goal. Consequently:

- an optimizing planner should converge toward the direct represented-set reference;
- a feasibility planner may return a more expensive path without violating its contract;
- a roadmap may discover an immediate direct connection and therefore reveal little independent structure;
- a planner timeout or poor finite-time solution is not evidence of physical unreachability;
- the absence of obstacles means this sprint does not establish routing performance in nonconvex free space.

The value of V4.2C is therefore not to manufacture a difficult planning problem. It is to establish exactly how planner-internal geometry responds to the transmission before collision topology is introduced.

No valid direct edge may be disabled merely to make a planner appear interesting.

## 4. Claims ladder

### 4.1 Required implementation claim

The Version 3 planning problem can be consumed by OMPL RRT*, BIT*, FMT, and geometric KPIECE without replacing the authoritative U-state, exact start, finite physical goal set, local-motion validator, actuator-travel objective, or result schema.

### 4.2 Required diagnostic claim

KPIECE can hold the physical planning state fixed in U while changing only the declared normalized exploration projection among U, Q, and X.

### 4.3 Allowed descriptive scientific claim

Under a frozen bounded audit, the planner portfolio exhibits specified differences in goal selection, first-solution behavior, convergence toward the direct reference, sampled graph/tree structure, and projection occupancy across the mechanism pair.

### 4.4 Prohibited claims

V4.2C may not claim:

- that one planner is universally best;
- that one mechanism universally makes planning easier;
- that a graph expansion, tree vertex, batch sample, projection cell, and wall-clock second are interchangeable effort units;
- that free-space behavior predicts obstacle-routing performance;
- that finite-time failure proves unreachability;
- that optional PDST results establish complete independence from metric or projection choices;
- that this sprint closes the deferred native-planner backlog.

## 5. Frozen physical planning contract

Every primary and diagnostic OMPL row must preserve the following:

| Contract element | Frozen V4.2C value |
| --- | --- |
| Physical state identity | complete `PhysicalState`, encoded to OMPL by actuator coordinate U |
| OMPL state space | bounded `RealVectorStateSpace(dim=2)` over certified U bounds |
| State distance | Euclidean distance in raw actuator coordinates U |
| State sampling, primary | uniform in raw U unless the row explicitly declares a frozen sampler diagnostic |
| Local motion | `InputLinearMotion` only |
| Motion validity | existing Version 3 continuous motion validator and counters |
| Objective | `ActuatorTravelObjective`, mapped exactly to OMPL path length under the frozen local-motion contract |
| Start | one exact physical start; no start tolerance or snapping |
| Goal | one frozen finite represented physical goal set with stable candidate IDs and ordering |
| Output coordinate | mounted robot joint coordinate from ADR-029; native follower coordinate is provenance only |
| Task predicate | unchanged physical Cartesian goal predicate from the V4.2B common-physical bank |
| Success | exact OMPL solution whose terminal physical state satisfies the Version 3 goal predicate |
| Approximate path | typed post-search `unsolved`; never promoted to success |
| Seed scope | one fresh process per planner/mechanism/task/repetition |
| Predecessor artifacts | immutable; V4.2C writes only its new guarded root |

A planner adapter must reject a problem it cannot honor. It may not silently fall back to ordinary output-joint planning, a weaker goal, endpoint-only validity, an approximate solution, or a different optimization objective.

## 6. Planner portfolio and scientific roles

### 6.1 Reference and deterministic controls

| Planner | Role | Required in retained report |
| --- | --- | --- |
| Input-linear direct represented-set reference | exact free-space actuator-travel reference over the frozen finite goal set | yes |
| Output-linear direct control | holds the visible Q path fixed and measures mechanism-specific actuator travel | yes |
| Eight-connected Dijkstra | deterministic graph cost-to-come baseline | yes |
| Eight-connected A* | deterministic represented-goal heuristic baseline | yes |

These are consumed from the corrected Version 3/V4.2B planning contract; V4.2C does not rewrite their implementations.

### 6.2 Existing OMPL architecture controls

| Planner | Role | Required in retained report |
| --- | --- | --- |
| OMPL PRM | roadmap-adapter and finite-goal compatibility control | yes, but not primary evidence |
| OMPL RRTConnect | first-feasible tree and exploration visualization control | yes, but not primary optimizing evidence |

The existing PRM multi-goal binding workaround must remain explicit. A sequential per-goal envelope is not relabeled as one true multi-goal solve.

### 6.3 Primary new optimizing planners

| Planner | Stable adapter ID | Scientific role |
| --- | --- | --- |
| OMPL RRT* | `ompl_rrt_star` | incremental optimizing tree; nearest-neighbor selection, parent choice, and rewiring |
| OMPL BIT* | `ompl_bit_star` | informed implicit random geometric graph; interaction of samples, cost ordering, and finite goal set |
| OMPL FMT | `ompl_fmt` | fixed-sample cost-to-come wavefront; sampled analogue of deterministic graph search |

The OMPL class is named `FMT`; documentation may describe it as the FMT* family, but result IDs and code names must use `ompl_fmt` to match the binding.

### 6.4 Required projection diagnostic

| Planner condition | Stable adapter ID | Only factor changed |
| --- | --- | --- |
| KPIECE with normalized U projection | `ompl_kpiece_u` | exploration projection |
| KPIECE with normalized Q projection | `ompl_kpiece_q` | exploration projection |
| KPIECE with normalized X projection | `ompl_kpiece_x` | exploration projection |

KPIECE is a diagnostic family, not an optimizing comparison. Its three conditions must share all nonprojection parameters.

### 6.5 Optional secondary control

Geometric PDST may be added as `ompl_pdst_u` only after the required portfolio is green and the Python binding capability probe passes. Its role is to test whether a pattern survives a path-directed subdivision strategy that does not use RRT*-style nearest-neighbor rewiring. It still depends on a projection, range, random sampling, and finite-time behavior; it is not described as completely metric independent.

PDST is nonblocking and may be reported as `unsupported_binding` without failing sprint closeout.

### 6.6 Explicitly deferred planners

Do not add in this sprint:

- ABIT*, AIT*, EIT*, Informed RRT*, or SORRT*;
- PRM*, Lazy PRM*, SPARS, or SPARS2;
- TSRRT or task-space inverse-lift planners;
- T-RRT, T-RRT*, CHOMP, STOMP, TrajOpt, or dynamics/control planners;
- native reimplementations of RRT*, BIT*, FMT, KPIECE, or PDST.

These remain candidate follow-ons after the first portfolio identifies an unresolved scientific question.

## 7. Planner-geometry record

Every OMPL result row and provenance record must include one complete planner-geometry declaration:

```python
@dataclass(frozen=True, slots=True)
class PlannerGeometryRecord:
    planner_role: str
    state_coordinates: str
    sampling_measure: str
    nearest_neighbor_distance: str | None
    optimization_objective: str
    cost_to_go_heuristic: str | None
    exploration_projection: str | None
    projection_normalization: str | None
    projection_cell_sizes: tuple[float, ...] | None
    goal_representation: str
    local_motion_model: str
```

Required canonical values include:

```text
state_coordinates: authoritative_u
nearest_neighbor_distance: euclidean_raw_u
optimization_objective: actuator_travel_euclidean_u
goal_representation: frozen_finite_physical_goal_set
local_motion_model: input_linear
```

The record belongs in common OMPL provenance, not scattered among planner-specific extras. Planner wrappers may add namespaced parameters but may not omit the common declaration.

## 8. Projection contract

The OMPL state remains U in all KPIECE conditions. Projection changes exploration bookkeeping only.

For a state \(u\), define:

### 8.1 Normalized U projection

\[
\pi_U(u)_i=\frac{u_i-u_{i,\min}}{u_{i,\max}-u_{i,\min}}.
\]

Bounds are exactly \([0,1]^2\).

### 8.2 Normalized mounted-Q projection

\[
q=g_m(u),
\qquad
\pi_Q(u)_i=\frac{q_i-q_{i,\min}}{q_{i,\max}-q_{i,\min}}.
\]

Only mounted robot joint coordinates may enter this projection.

### 8.3 Normalized Cartesian-X projection

\[
x=f(g_m(u)).
\]

The X projection uses a deterministic, pre-outcome bounding box computed from the shared mounted-Q case domain. The same X normalization is used for both mechanisms within a case. Degenerate dimensions fail closed.

### 8.4 Cell-size policy

Projection cell sizes are explicit; OMPL inference is not accepted in retained evidence. Calibration operates on normalized coordinates using a frozen candidate set such as:

```text
cells_per_axis: [8, 12, 16, 24]
```

Selection uses occupancy-health criteria on null/control runs before paired comparative outcomes are inspected. The selected value and the complete rejected calibration table are retained.

The U/Q/X ablation changes only:

```text
exploration_projection
projection_normalization
projection_bounds
```

Planner range, goal bias, border fraction, minimum valid path fraction, task, seed, solve budget, local motion, and objective remain fixed.

## 9. Sampling, randomness, and process isolation

### 9.1 Primary sampling measure

The primary planner portfolio samples uniformly in raw U. This preserves the current physical actuator formulation. Uniform-Q or uniform-X sampling is not introduced into the primary comparison.

### 9.2 Normalized paired sample diagnostic

A frozen normalized-U sample-sequence diagnostic may be implemented when the installed Python binding exposes a safe state-sampler allocator. Candidate implementations are:

- a project-owned normalized-fraction sampler;
- OMPL `PrecomputedStateSampler`;
- OMPL deterministic/Halton sampling.

This diagnostic must be capability-gated. If the binding cannot safely own allocated states or install the sampler, record `unsupported_binding`; do not emulate a frozen bank by changing planner internals.

### 9.3 Seed protocol

OMPL's RNG seed is process-global in the current adapter. Every stochastic run therefore executes in a fresh worker process and records:

- requested seed;
- repetition index;
- process-isolated status;
- whether the seed API was exposed and called;
- OMPL version;
- Python version and platform;
- planner configuration digest;
- task and mechanism identifiers.

Reproducibility is tested empirically under the frozen environment. It is not inferred from the planner name.

## 10. Budget and convergence contract

One scalar wall-time budget is not sufficient for every planner family.

### 10.1 RRT* and BIT*

Use cumulative solve checkpoints in one fresh process, where supported, for example:

```text
0.05 s, 0.10 s, 0.25 s, 0.50 s, 1.00 s, 2.00 s
```

At every checkpoint, retain:

- exact-solution status;
- best objective cost;
- selected goal candidate;
- direct-reference gap;
- PlannerData counts;
- validity counters;
- exposed planner progress properties.

The final calibrated ladder is frozen before the retained paired audit.

### 10.2 FMT

FMT is controlled primarily by sample count rather than by pretending it is an anytime tree. Use independent process-isolated runs over a frozen sample-count ladder such as:

```text
64, 128, 256, 512, 1024
```

Primary settings:

- `nearest_k = true` unless calibration rejects it for a documented binding or connectivity reason;
- `radius_multiplier > 1` when radius mode is used;
- `heuristics = true` in the primary condition;
- `extended_fmt = false` in the primary condition;
- a separate `heuristics=false` ablation is allowed and must be labeled.

### 10.3 KPIECE, PRM, RRTConnect, and optional PDST

Use a calibrated fixed solve budget. Their path costs are reported, but they are not pooled with asymptotic-optimizer convergence curves.

### 10.4 Parameter normalization

Distance-like parameters such as planner range are specified as fractions of the OMPL state-space maximum extent and resolved per mechanism. Dimensionless parameters are held identical across paired arms.

No parameter may be tuned separately for the four-bar and gearbox after comparative outcomes are visible.

## 11. Evidence stages

## 11.1 Stage A — binding and contract smoke

Minimum corpus:

- one corrected V4.2B case;
- one near and one far task;
- both mechanisms;
- one process-isolated seed;
- all required planner IDs.

Purpose:

- prove construction, exact start, multi-goal handling, objective equivalence, projection callbacks, result serialization, and typed failure behavior.

No comparative claim is allowed.

## 11.2 Stage B — calibration

Freeze before paired audit:

- three predeclared span cases: compact symmetric, biological symmetric, and mixed-span;
- two near and two far tasks selected by task ID, not planner outcome;
- at least five process-isolated repetitions;
- the candidate range, cell-size, samples-per-batch, FMT sample-count, and solve-budget ladders.

Calibration objectives are implementation health rather than mechanism advantage:

- avoid universal timeout;
- avoid immediate saturation at the smallest budget;
- avoid empty or single-cell KPIECE projections;
- preserve exact-goal and objective contracts;
- keep retained package size bounded.

Freeze the selected configuration and digest before Stage C.

## 11.3 Stage C — retained planner audit

Required bounded corpus:

- five predeclared span cases:
  1. compact symmetric;
  2. biological symmetric;
  3. high-span symmetric or typed boundary-stress case;
  4. compact/high mixed-span;
  5. biological mixed-span;
- all ten V4.2B common-physical task IDs;
- both mechanisms;
- ten process-isolated repetitions for stochastic planner conditions;
- deterministic controls once per mechanism-task;
- required primary and projection conditions;
- optional PDST reported separately.

Case IDs are resolved from the frozen registry and written to the config before planner outcomes. A typed boundary-stress case remains stratified and is not pooled with ordinary cases.

The retained package is descriptive. It reports paired distributions and convergence summaries but does not perform a production population inference.

## 11.4 Stage D — optional all-case descriptive sweep

A `--all-cases` mode may evaluate all 17 corrected V4.2B cases after Stage C closes. It is not required for V4.2C exit and may not be generated opportunistically during implementation.

## 12. Common and family-specific metrics

### 12.1 Common metrics

Every row records, where meaningful:

- task class and paired direct-feasibility stratum;
- exact-solution status and failure taxonomy;
- exact start residual;
- selected goal candidate ID and provenance;
- physical task residual and goal margin;
- objective cost;
- direct represented-set reference cost;
- absolute and relative suboptimality;
- U, Q, and X path lengths evaluated through the declared continuous connector;
- setup, preprocessing, query, postprocessing, and total wall time;
- state and motion validity checks;
- planner-geometry record;
- seed/process/version provenance.

### 12.2 Optimizer metrics

RRT* and BIT* additionally record:

- first exact-solution time and cost;
- best cost at each checkpoint;
- final reference gap;
- number of cost improvements;
- PlannerData vertices and edges at each checkpoint;
- available OMPL progress properties.

FMT additionally records:

- requested and effective sample counts;
- nearest-K/radius policy;
- radius multiplier;
- heuristic and extended-FMT flags;
- vertices/edges and final reference gap.

### 12.3 Projection-planner metrics

KPIECE rows additionally record:

- projection ID and formula;
- projection bounds and cell sizes;
- occupied/boundary-cell counts when exposed;
- PlannerData vertices/edges;
- extension and validity counters available through the adapter.

If a binding does not expose cell counts, report the missing capability explicitly. Do not reconstruct an alleged internal cell history from final path points.

### 12.4 Metrics that may not be pooled

Do not combine into one scalar:

- Dijkstra/A* expansions;
- PRM/FMT samples or roadmap vertices;
- RRT-family tree vertices or rewires;
- BIT* batches or queue operations;
- KPIECE occupied cells;
- validity-check counts;
- wall-clock time.

The root report is organized by scientific question and planner family, not by one global rank ordering.

## 13. Required artifact structure

```text
results/v4_review/v4_2c_ompl_planner_portfolio/
├── manifest.json
├── resolved_config.json
├── capability_matrix.json
├── calibration/
│   ├── rows.jsonl.gz
│   └── selection.json
├── audit/
│   ├── deterministic_controls.jsonl.gz
│   ├── stochastic_rows.jsonl.gz
│   ├── convergence_checkpoints.jsonl.gz
│   └── failures.jsonl.gz
├── planners/
│   ├── rrt_star/
│   ├── bit_star/
│   ├── fmt/
│   ├── kpiece_u/
│   ├── kpiece_q/
│   ├── kpiece_x/
│   ├── prm_control/
│   ├── rrt_connect_control/
│   └── pdst_optional/
├── cases/
├── methods/
│   ├── planner_geometry_contract.md
│   ├── projection_definitions.md
│   └── calibration_and_budget_policy.md
├── summary.json
├── index.html
└── README.md
```

Large row sets are compressed and hashed. The manifest records every retained file digest. No required evidence may exist only in HTML.

## 14. Work packages

## V4-230 — Contract landing, ADR, and artifact guard

### Implementation

- Land ADR-031, this sprint, the V4 sprint-index amendments, project-plan amendments, and the Cursor guide in a planning-only commit.
- After separate activation, extend `v4_artifact_guard.py` with exactly one new writable root:

```text
results/v4_review/v4_2c_ompl_planner_portfolio/
```

- Refuse writes into V4.0–V4.2B, every `results/v3_review/` package, V4.3+, sibling V4 roots, and arbitrary paths.
- Retain and verify digests for the corrected V4.2B package consumed by this sprint.

### Tests

- allowed root and nested paths succeed;
- historical and arbitrary paths fail closed;
- a tmp export leaves every predecessor artifact byte-unchanged;
- the planning patch itself does not edit `ACTIVE_SPRINT.md`.

### Exit

V4.2C has one fresh artifact lineage and a frozen architecture decision without activating source work prematurely.

## V4-231 — OMPL 2.0.1 Python-binding capability matrix

### Implementation

Add a probe module and script that discovers, without running the retained experiment:

- OMPL version;
- presence of geometric `RRTstar`, `BITstar`, `FMT`, `KPIECE1`, `PDST`;
- exposed setter/getter methods required by the sprint;
- safe construction of a Python projection evaluator;
- explicit projection cell sizes and bounds;
- multi-state `GoalStates` behavior for each planner in a fresh process;
- repeated `solve()` continuation behavior;
- PlannerData and planner-progress property access;
- state-sampler allocator, precomputed sampler, and deterministic sampler exposure;
- exact-solution detection.

Suggested files:

```text
src/inequality_mechanisms/adapters/ompl/capabilities.py
scripts/probe_v4_2c_ompl_capabilities.py
```

Each probe has a timeout and produces a typed result rather than hanging the parent process.

### Tests

- core package import remains OMPL-free;
- missing OMPL returns a complete `unavailable_dependency` matrix;
- an OMPL-enabled environment records the version and every required symbol;
- a hanging or crashing child probe becomes a typed failure;
- optional PDST/sampler capabilities do not block required planners.

### Exit

The implementation is driven by the actual Python binding surface rather than assumptions from C++ documentation.

## V4-232 — Shared OMPL planner-geometry and solve-session refactor

### Implementation

Refactor the current `solve_with_ompl_planner` path into composable pieces without changing existing PRM/RRTConnect behavior:

```text
build_ompl_session(problem, adapter_config)
configure_goal(session, frozen_candidates)
configure_objective(session)
run_single_shot(session, planner)
run_checkpointed(session, planner, checkpoints)
finalize_ompl_result(session, planner, path)
```

Add:

```text
src/inequality_mechanisms/adapters/ompl/planner_geometry.py
src/inequality_mechanisms/adapters/ompl/session.py
```

Requirements:

- one common `PlannerGeometryRecord`;
- exact-start canonicalization remains fail-closed;
- finite goal candidate identity survives result assembly;
- existing state/motion validity counters survive;
- approximate solutions remain unsolved;
- existing `OmplPRMPlanner` and `OmplRRTConnectPlanner` wrappers remain API-compatible;
- sequential PRM goal handling remains explicitly identified;
- one final or checkpointed PlannerData snapshot path is shared.

### Tests

- V3.5 optional-gate and adapter tests remain green;
- V3.6 process-isolated PRM/RRTConnect records are schema-compatible;
- existing planner IDs and capabilities do not drift;
- objective cost equals integrated actuator travel;
- selected candidate provenance is retained;
- unsupported local motion/objective still fails before planner construction.

### Exit

New planners can share one authoritative adapter boundary without copy-pasting task, objective, or result semantics.

## V4-233 — RRT*, BIT*, and FMT adapters

### Implementation

Add thin wrappers:

```text
src/inequality_mechanisms/adapters/ompl/rrt_star.py
src/inequality_mechanisms/adapters/ompl/bit_star.py
src/inequality_mechanisms/adapters/ompl/fmt.py
```

Expose lazily through `adapters/ompl/__init__.py`.

#### RRT* configuration

- normalized range fraction;
- goal bias;
- rewire factor;
- K-nearest/radius mode when exposed;
- delayed collision checking flag;
- pruning/informed options remain off in the primary plain-RRT* condition unless separately labeled.

#### BIT* configuration

- samples per batch;
- rewire factor;
- K-nearest/radius mode;
- pruning flag;
- strict queue ordering when exposed;
- primary condition uses the existing path-length objective and its admissible cost structure.

#### FMT configuration

- sample count;
- nearest-K/radius mode;
- radius multiplier;
- heuristic flag;
- extended-FMT flag;
- collision-check cache flag.

All binding-specific method calls are guarded by the V4-231 capability record. Missing required methods cause a typed adapter rejection; they do not silently use unknown defaults in retained evidence.

### Tests

For each required planner:

- lazy import without OMPL;
- capability metadata truthfulness;
- construction and parameter round trip where getters exist;
- exact start;
- one finite goal and multiple finite goals;
- exact-solution fail-closed behavior;
- actuator-cost agreement;
- deterministic fixture success under a generous bounded smoke;
- typed failure when a required binding method is absent.

### Exit

The three required optimizing families consume the unchanged Version 3 problem and return comparable common results plus namespaced planner metrics.

## V4-234 — Normalized U/Q/X projection evaluators and KPIECE

### Implementation

Add:

```text
src/inequality_mechanisms/adapters/ompl/projections.py
src/inequality_mechanisms/adapters/ompl/kpiece.py
```

Implement one reusable physical projection evaluator with strategies:

```text
normalized_u
normalized_mounted_q
normalized_cartesian_x
```

Requirements:

- projection callback begins from OMPL U, reconstructs authoritative `PhysicalState`, and then reads mounted Q or FK X;
- explicit bounds and cell sizes;
- no native follower angle;
- deterministic X bounds derived before planner outcomes;
- projection errors fail the run with task/mechanism/projection IDs;
- KPIECE parameters are common across the three projection arms;
- U/Q/X rows differ only in the projection declaration.

### Tests

- analytic projection values at bounds and midpoint;
- same Q/X projection for paired mechanisms at the same shared physical Q state;
- mechanism-specific U projection when the inverse maps differ;
- finite-difference continuity away from known boundaries;
- degenerate bounds rejected;
- exact same nonprojection config digest across the U/Q/X ablation;
- explicit cell sizes reported as user configured.

### Exit

The project can directly visualize how one physical planner perceives exploration under U, Q, and X without changing state identity or objective.

## V4-235 — Sampling controls, process isolation, and optional PDST

### Implementation

- Add a V4.2C process worker that accepts one complete request and writes one atomic result.
- Reuse the process isolation principle from V3.6 but remove planner-specific branching from the worker through a registry.
- Implement optional normalized-fraction/precomputed sampling only when V4-231 proves safe binding support.
- Add optional geometric PDST with normalized-U projection after required planner tests pass.

Suggested files:

```text
src/inequality_mechanisms/benchmarks/ompl_process_worker_v4_2c.py
src/inequality_mechanisms/adapters/ompl/sampling.py
src/inequality_mechanisms/adapters/ompl/pdst.py
```

The worker records stdout/stderr, child exit status, timeout status, request digest, and environment. Partial files are not counted as completed rows.

### Tests

- same request/seed in two fresh processes is compared and reproducibility status recorded;
- child timeout and crash are typed;
- failed attempts are retained separately;
- atomic write prevents a truncated row from appearing complete;
- optional sampler and PDST absence do not fail required closeout;
- no in-process multi-repetition reproducibility claim remains.

### Exit

Stochastic evidence has a stable process boundary, and optional controls cannot destabilize the required portfolio.

## V4-236 — Checkpointed optimization and namespaced instrumentation

### Implementation

Extend OMPL metrics beyond one final vertex/edge count:

```text
src/inequality_mechanisms/adapters/ompl/metrics.py
```

Add:

- common PlannerData snapshots;
- cumulative checkpoint records for RRT*/BIT*;
- independent sample-count records for FMT;
- exposed planner progress properties;
- first exact-solution time and cost;
- best-cost improvement sequence;
- projection metadata and exposed KPIECE cell statistics;
- resolved parameter values from getters where available.

Do not claim unavailable internal events. Fields unsupported by the binding are `null` with a reason, not zero.

### Tests

- checkpoint times strictly increase;
- best exact cost is nonincreasing across optimizer checkpoints;
- FMT sample-count rows remain independent runs;
- no family-specific metric leaks into the common namespace;
- final common objective matches the last exact checkpoint;
- serialization is deterministic.

### Exit

The retained report can compare convergence and planner structure without inventing a cross-family work unit.

## V4-237 — Frozen configs, runner, and evidence stages

### Implementation

Add strict Pydantic configuration with `extra="forbid"` and separate modes:

```text
configs/v4/ompl_planner_portfolio_smoke_v1.json
configs/v4/ompl_planner_portfolio_calibration_v1.json
configs/v4/ompl_planner_portfolio_audit_v1.json
```

Add:

```text
src/inequality_mechanisms/experiments/v4/ompl_planner_portfolio.py
scripts/generate_v4_2c_ompl_planner_portfolio.py
```

Requirements:

- consume V4.2B through its manifest/public loaders;
- lock V4.2B source digest;
- resolve and freeze case IDs before execution;
- retain all task IDs and failure rows;
- support resume only by exact request digest;
- refuse config drift within an output root;
- keep Stage A/B/C outputs separate;
- require a frozen calibration selection before audit mode;
- optional all-case mode writes to a separate nonrequired subpackage.

### Tests

- strict schema rejection;
- deterministic request matrix and row count;
- no task/case replacement after outcomes;
- resume skips only exact completed requests;
- failed child rows are not marked completed;
- source artifact digest mismatch fails before planning;
- smoke fixtures use `tmp_path` and bounded budgets.

### Exit

One versioned command can reproduce a bounded, process-isolated portfolio without ad hoc notebooks or planner-specific task logic.

## V4-238 — HTML/JSON evidence report grouped by question

### Implementation

Add report code under:

```text
src/inequality_mechanisms/visualization/v4/ompl_planner_portfolio.py
```

Root report sections:

1. contract and capability matrix;
2. frozen case/task/repetition matrix;
3. direct and deterministic references;
4. optimizer convergence: RRT*, BIT*, FMT;
5. KPIECE U/Q/X projection ablation;
6. PRM/RRTConnect controls;
7. optional PDST;
8. task classes, failures, and unsupported capabilities;
9. mechanism-paired summaries by case and task;
10. methods, provenance, and nonclaims.

Required visuals:

- best-cost/reference-gap curves with repetition bands;
- first-solution versus final-cost scatter;
- selected-goal-candidate distributions;
- PlannerData growth curves where meaningful;
- synchronized U/Q/X final path views for selected rows;
- KPIECE projection occupancy/grid views when exposed;
- paired four-bar-minus-gearbox effects within the same planner condition;
- no global winner table.

### Tests

- report reads only retained machine-readable files;
- every plotted row links to task/mechanism/planner/repetition provenance;
- unsupported planners remain visible;
- family-specific units are labeled;
- link integrity and deterministic summary regeneration;
- report includes the free-space interpretation boundary and prohibited claims.

### Exit

A reviewer can understand what each planner tests, how the mechanism entered it, and what the result does not establish.

## V4-239 — Full regression, retained artifact, review, and authorization reset

### Required gates

1. Core package imports and full non-OMPL tests pass without OMPL installed.
2. Existing V3.5/V3.6 OMPL tests pass in the OMPL-enabled environment.
3. Required V4.2C planner and projection tests pass.
4. V4.0–V4.2B and all V3 retained package digests remain unchanged.
5. Stage A and Stage B complete with reviewed calibration selection.
6. Stage C retained package is generated from a clean implementation revision.
7. Manifest, compressed data, hashes, HTML links, and row counts verify.
8. A closeout note records supported and unsupported binding features, deviations from the drafted config, and every nonclaim.
9. `ACTIVE_SPRINT.md` returns to no authorization in a separate closeout change.
10. V4.3 is not activated in the V4.2C closeout commit.

### Exit

V4.2C closes with one immutable diagnostic artifact and a documented decision on which planner families should enter the later application-integrated planning column.

## 15. Configuration schema sketch

```json
{
  "schema_version": "v4_2c_ompl_planner_portfolio_v1",
  "source": {
    "v4_2b_manifest_sha256": "<required>",
    "ompl_version_required": "2.0.1"
  },
  "mode": "smoke|calibration|audit|all_cases_optional",
  "case_ids": ["<frozen before run>"],
  "task_ids": ["near_0", "near_1", "near_2", "near_3", "near_4", "far_0", "far_1", "far_2", "far_3", "far_4"],
  "mechanisms": ["fourbar", "gearbox"],
  "repetitions": 10,
  "seed_base": 7,
  "physical_contract": {
    "state_coordinates": "authoritative_u",
    "local_motion": "input_linear",
    "objective": "actuator_travel_euclidean_u",
    "goal_representation": "frozen_finite_physical_goal_set"
  },
  "planners": {
    "ompl_rrt_star": {},
    "ompl_bit_star": {},
    "ompl_fmt": {},
    "ompl_kpiece_u": {},
    "ompl_kpiece_q": {},
    "ompl_kpiece_x": {},
    "ompl_prm": {"role": "control"},
    "ompl_rrt_connect": {"role": "control"},
    "ompl_pdst_u": {"enabled": false, "required": false}
  }
}
```

The shipped schema must contain typed nested planner settings rather than unvalidated free-form dictionaries. The sketch only identifies the required structure.

## 16. Recommended implementation order

```text
V4-230 contract/guard
→ V4-231 binding probe
→ V4-232 shared session refactor
→ V4-233 RRT*/BIT*/FMT
→ V4-234 U/Q/X KPIECE
→ V4-235 process/sampler/optional-PDST controls
→ V4-236 checkpoint metrics
→ V4-237 staged runner
→ V4-238 report
→ V4-239 retained evidence and closeout
```

Do not start the report before the row schema and checkpoint semantics are green. Do not start the retained audit before calibration is frozen.

## 17. Sprint exit criteria

V4.2C is complete only when:

1. ADR-031 is accepted and every OMPL row serializes a complete planner-geometry record.
2. OMPL RRT*, BIT*, FMT, and KPIECE-U/Q/X consume the unchanged Version 3 planning problem.
3. U remains authoritative state identity; Q and X appear only as projections, tasks, metrics, and interpretations.
4. Exact start, frozen finite goals, candidate provenance, local motion, validity, and actuator objective remain common.
5. RRT*/BIT* convergence and FMT sample-count behavior are recorded against the direct represented-set reference.
6. KPIECE U/Q/X conditions differ only in the frozen projection fields.
7. PRM and RRTConnect remain visible architecture controls without being treated as primary mechanism evidence.
8. Optional PDST and sampler features are capability-gated and nonblocking.
9. Family-specific metrics remain namespaced and no global effort leaderboard is emitted.
10. The retained Stage C package is complete, hashed, reproducible from one command, and does not mutate predecessor artifacts.
11. The closeout states explicitly that the sprint is descriptive free-space evidence, not obstacle-routing or universal planner superiority.
12. Authorization is reset without automatically activating V4.3.

## 18. Compact Cursor handoff

> Implement only Sprint V4.2C work packages V4-230–V4-239 after `ACTIVE_SPRINT.md` explicitly authorizes that range and only after V4.2B has closed. Preserve the Version 3 `PlanningProblem` and `PlanningResult` contracts. Keep physical state in U, `InputLinearMotion`, `ActuatorTravelObjective`, exact start, the frozen V4.2B finite goal set, mounted Q from ADR-029, and existing validity callbacks authoritative. Add OMPL RRT*, BIT*, FMT, and geometric KPIECE with normalized U/Q/X projection conditions; keep PRM/RRTConnect as controls; make PDST and custom samplers optional capability-gated work. Add a complete planner-geometry provenance record, process-isolated workers, checkpointed optimizer metrics, strict staged configs, a bounded retained artifact, and an HTML report grouped by scientific question rather than a global leaderboard. Do not edit frozen evidence, implement obstacles/MoveIt/3R/6R, add native copies of OMPL planners, disable valid direct edges, or activate V4.3 in the closeout.

## 19. OMPL references used by the sprint contract

- OMPL 2.0.1 home and planner index: <https://ompl.kavrakilab.org/>
- RRT*: <https://ompl.kavrakilab.org/classompl_1_1geometric_1_1RRTstar.html>
- BIT*: <https://ompl.kavrakilab.org/classompl_1_1geometric_1_1BITstar.html>
- FMT: <https://ompl.kavrakilab.org/classompl_1_1geometric_1_1FMT.html>
- Geometric KPIECE1: <https://ompl.kavrakilab.org/classompl_1_1geometric_1_1KPIECE1.html>
- Geometric PDST: <https://ompl.kavrakilab.org/classompl_1_1geometric_1_1PDST.html>
- Projection evaluator: <https://ompl.kavrakilab.org/classompl_1_1base_1_1ProjectionEvaluator.html>
- State-space sampler allocator: <https://ompl.kavrakilab.org/classompl_1_1base_1_1StateSpace.html>
- Precomputed sampler: <https://ompl.kavrakilab.org/classompl_1_1base_1_1PrecomputedStateSampler.html>
