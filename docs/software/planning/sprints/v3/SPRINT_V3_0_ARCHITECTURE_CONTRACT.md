# Sprint V3.0 — Architecture Contract and V2 Evidence Freeze

**Status:** deliverables drafted / pending review acceptance  
**Code authorization:** none until V3.1 is explicitly activated  
**Primary deliverable:** proposed V3 contracts and migration map  
**Reference:** [`V3_PROJECT_PLAN.md`](../../../V3_PROJECT_PLAN.md)

## Sprint intent

Freeze the trusted Version 2 evidence lineage and define the planner-independent contracts required for Version 3.

This sprint is deliberately architecture-first. It does not implement new planners, obstacles, OMPL, MoveIt, higher-DOF robots, or a new Monte Carlo campaign.

## Why this sprint exists

The Version 2 Monte Carlo and A* campaigns revealed formulation choices that must not be carried forward as universal assumptions:

- fixed normalized \(Q\)-space query lengths are diagnostic tasks, not the primary robot-task distribution;
- start tolerance is a lattice attachment approximation, not application semantics;
- four-connected one-coordinate-at-a-time motion is not a general robot local-motion model;
- node expansions are not a universal planner metric;
- relative log ratios can obscure absolute computational importance;
- free-space direct/local tasks must be distinguished from tasks requiring global planning;
- production orchestration cannot precede stable task, planner, scene, and statistical contracts.

## Entry conditions

1. V2.10 and V2.11 reports remain reproducible.
2. The bounded Experiment B smoke/calibration work is preserved but no production campaign is authorized.
3. The project accepts a V3 architectural pivot rather than extending V2 orchestration opportunistically.

## Non-goals

- no source-module reorganization;
- no API break;
- no planner implementation;
- no obstacle implementation;
- no task-bank generation;
- no OMPL or ROS dependency;
- no MoveIt workspace;
- no new performance claim;
- no ADR renumbering before the current branch index is synchronized.

## Work packages

### V3-000 — Freeze the Version 2 evidence lineage

Record:

- trusted code revision or tag;
- authoritative Experiment A protocols and reports;
- bounded Experiment B artifacts and their non-production status;
- configuration and result-schema versions;
- known formulation limitations;
- files that must remain reproducible.

**Deliverable:** [`docs/software/experiments/reports/V2_EVIDENCE_FREEZE.md`](../../../experiments/reports/V2_EVIDENCE_FREEZE.md).

### V3-001 — Call-site and dependency inventory

Inventory current responsibilities and coupling across:

- mechanisms and operating branches;
- output-state graphs;
- query overlays;
- local edge validation;
- objectives and heuristics;
- Dijkstra/A* core;
- Cartesian task sampling;
- runners, configs, schemas, analysis, and visualization.

For each module, classify:

- reusable unchanged;
- reusable through adapter;
- requires refactor;
- legacy-only;
- obsolete after migration.

**Deliverable:** [`docs/software/architecture/notes/V3_CODE_INVENTORY.md`](../../../architecture/notes/V3_CODE_INVENTORY.md).

### V3-002 — Planning problem contract

Freeze interfaces for:

- `PhysicalState`;
- `RobotModel`;
- `PlanningScene`;
- `GoalConstraint`;
- `ConstraintSet`;
- `LocalMotionModel`;
- `PlanningObjective`;
- `Planner`;
- `PlanningResult`.

The contract must support direct, graph, roadmap, tree, OMPL, and later MoveIt backends without planner-specific fields in the problem definition.

**Deliverable:** [ADR-021](../../../architecture/adr/ADR-021-v3-planning-problem-contract.md) (proposed).

### V3-003 — State and representation contract

Freeze the distinction between:

- physical state \((u,q,\text{branch},\ldots)\);
- planner representation;
- task-space pose;
- graph or planner internal state.

Document the initial monotonic-branch comparative special case and the later noninjective-state requirement.

**Deliverable:** [ADR-022](../../../architecture/adr/ADR-022-v3-state-and-representation.md) (proposed).

### V3-004 — Exact start and goal-region contract

Freeze:

- exact start state semantics;
- query attachment for graph/roadmap planners;
- tree root semantics;
- Cartesian goal predicates;
- goal tolerance reporting;
- selected goal-state reporting;
- IK-family handling.

Explicitly remove `start_tolerance` as a task parameter. Any numerical attachment residual is an algorithm diagnostic.

**Deliverable:** [ADR-023](../../../architecture/adr/ADR-023-v3-exact-start-and-goal-regions.md) (proposed).

### V3-005 — Local motion and cost contract

Freeze:

- output-linear local motion;
- input-linear local motion;
- continuous state and motion validation;
- integrated actuator-path cost;
- endpoint-cost approximation tests;
- simultaneous joint motion;
- graph adjacency as candidate generation rather than physical-motion definition.

**Deliverable:** [ADR-024](../../../architecture/adr/ADR-024-v3-local-motion-and-cost.md) (proposed).

### V3-006 — Planner capability and adapter contract

Define capability metadata such as:

```python
@dataclass(frozen=True)
class PlannerCapabilities:
    deterministic: bool
    multi_query: bool
    optimizing: bool
    supports_goal_region: bool
    supports_path_constraints: bool
    reports_graph_exploration: bool
    supports_exact_start: bool
```

Define native and external adapter boundaries, including OMPL first and MoveIt later.

**Deliverable:** [ADR-025](../../../architecture/adr/ADR-025-v3-planner-capabilities-and-adapters.md) (proposed).

### V3-007 — Benchmark classification and metrics contract

Freeze pre-benchmark classes:

- already satisfied;
- direct/local feasible;
- global planning required;
- invalid/unreachable.

Freeze common metrics and planner-specific metric namespaces.

Require paired relative and absolute effects:

- log ratios;
- absolute count differences;
- wall-time differences;
- objective-cost differences.

Preserve the Q-spanner as a separate diagnostic protocol.

**Deliverable:** [ADR-026](../../../architecture/adr/ADR-026-v3-benchmark-classification-and-metrics.md) (proposed) and benchmark-schema semantic draft therein.

### V3-008 — Migration and golden-compatibility plan

Define one compatibility fixture that can run through:

- the frozen V2 stack;
- V3 adapters around the existing mechanism and search implementations.

The fixture must agree on declared states, path cost, selected goal, and search instrumentation where semantics are identical.

**Deliverable:** [`docs/software/architecture/notes/V3_MIGRATION_MAP.md`](../../../architecture/notes/V3_MIGRATION_MAP.md).

### V3-009 — Sprint and issue decomposition

Write bounded sprint files for V3.1 and V3.2 only after contracts are drafted.

Later roadmap milestones remain non-executable until separately specified.

**Deliverables:** [SPRINT_V3_1_CORE_PROBLEM_RESULT_MODEL.md](SPRINT_V3_1_CORE_PROBLEM_RESULT_MODEL.md), [SPRINT_V3_2_DIRECT_2R_VERTICAL_SLICE.md](SPRINT_V3_2_DIRECT_2R_VERTICAL_SLICE.md) (drafted; not activated).

## Required review questions

1. Does the problem contract describe the robot task independently of a planner?
2. Can the same problem be consumed by direct, graph, roadmap, and tree planners?
3. Is \(U\rightarrow Q\rightarrow X\) explicit in every relevant contract?
4. Are exact start and goal tolerance semantics unambiguous?
5. Is local motion continuous and independent of lattice indexing?
6. Are common metrics meaningful across planner families?
7. Are planner-specific metrics namespaced rather than forced into one schema?
8. Is the Q-spanner preserved without contaminating application-task estimands?
9. Is production Monte Carlo explicitly blocked?
10. Can stable V2 modules migrate through adapters without deletion or reinterpretation?

## Exit criteria

Sprint V3.0 is complete when:

1. the V2 evidence freeze document is accepted;
2. the current code inventory is complete;
3. all V3 core interfaces have accepted contracts;
4. exact-start and Cartesian goal-region semantics are frozen;
5. simultaneous local motion and integrated mechanism-aware cost are frozen;
6. the benchmark classification and metric contract is accepted;
7. OMPL and MoveIt boundaries are explicit and distinct;
8. the V3 migration map and compatibility fixture are specified;
9. V3.1 and V3.2 sprint documents exist;
10. no production campaign or obstacle sprint has been activated.

## Handoff

After acceptance of the V3.0 deliverables, activate V3.1 to implement only the core problem/result model and compatibility adapters. V3.1 and V3.2 sprint stubs are drafted and remain inactive until explicitly authorized.
