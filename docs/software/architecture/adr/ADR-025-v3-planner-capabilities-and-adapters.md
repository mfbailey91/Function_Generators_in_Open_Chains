# ADR-025 — Version 3 planner capability and adapter contract

**Status:** Accepted  
**Applies to:** Version 3  
**Related:** ADR-005, ADR-021, ADR-024; Sprint V3.0 V3-006  
**Supersedes:** nothing

## Context

Node expansions are meaningful for deterministic graph search and not for every planner family. External stacks (OMPL, MoveIt) provide mature algorithms but must not become the source of truth for mechanism state or silently replace mechanism-aware metrics with ordinary joint distance.

## Decision

### Capability metadata

Every planner declares:

```python
@dataclass(frozen=True)
class PlannerCapabilities:
    deterministic: bool
    reproducible_with_seed: bool
    multi_query: bool
    optimizing: bool
    probabilistically_complete: bool | None
    asymptotically_optimal: bool | None
    requires_metric_space: bool
    supports_optimization_objective: bool
    supports_goal_region: bool
    supports_goal_sampling: bool
    supports_multi_start: bool
    supports_path_constraints: bool
    supports_approximate_solution: bool
    supports_incremental_solutions: bool
    reports_graph_exploration: bool
    supports_exact_start: bool
```

`deterministic` describes the algorithm under fixed inputs. `reproducible_with_seed` states whether a frozen seed, task, configuration, and implementation revision are expected to reproduce the same result. Neither field excuses missing seed and provenance records.

Optional or unknown theoretical properties use `None` rather than a guessed boolean:

- `probabilistically_complete` and `asymptotically_optimal` may be `None` for native prototypes, thin wrappers, or planners whose guarantees are not claimed under the Version 3 formulation;
- boolean support flags (`supports_*`) must be honest for the adapter as shipped: `False` means unsupported, not “not yet declared”;
- V3.1 graph and direct adapters are not blocked on filling completeness or optimality claims; they may leave those fields `None` until a later sprint documents a guarantee.

### Planner lifecycle metadata

Multi-query planners must declare how preprocessing is managed:

```python
class PlannerLifecycle(str, Enum):
    SINGLE_QUERY = "single_query"
    BUILD_PER_TASK = "build_per_task"
    REUSE_WITHIN_RUN = "reuse_within_run"
    LOAD_FROZEN_STRUCTURE = "load_frozen_structure"
```

Roadmap construction, loading, query attachment, search, and postprocessing times are reported separately. Any amortized query-time claim must declare the number and distribution of queries over which preprocessing is amortized.

### Native planner families (roadmap order)

1. Direct reference planners (output-linear, input-linear; later Cartesian-linear).
2. Native deterministic graph / lattice planners (BFS diagnostics, Dijkstra, A*, weighted A*, bidirectional variants, any-angle).
3. Native roadmap planners (PRM, Lazy PRM, PRM*).
4. Native tree planners (RRT, RRTConnect, RRT*).
5. Informed / batch planners after core parity (BIT*, FMT* or equivalent).
6. Trajectory optimization and industrial generators via adapters later (CHOMP, STOMP, Pilz, etc.).

### OMPL adapter — algorithm validation

OMPL is the first external backend. The adapter maps Version 3 concepts to OMPL `StateSpace`, bounds, `StateValidityChecker`, `MotionValidator`, goal regions, `OptimizationObjective`, and `ProblemDefinition`. The Version 3 framework remains authoritative for \(U\rightarrow Q\rightarrow X\), tasks, objectives, validity, and benchmark records.

### MoveIt adapter — application validation

MoveIt comes later for URDF/SRDF robots, planning scenes, collision, and application pipelines. The first integration is an outbound `MoveItPipelineAdapter`. A mechanism-aware MoveIt planner plugin is optional later. MoveIt must not silently replace the mechanism-aware metric or hide mechanism state.

### Adapter boundary

Native and external adapters consume `PlanningProblem` and return `PlanningResult`. Planner-specific fields belong in capabilities, lifecycle/configuration, and `planner_metrics`, never in the problem definition.

An adapter must reject a problem when the planner cannot honor required task, state, validity, objective, or exact-start semantics. It must not silently project the problem onto a weaker ordinary-joint formulation.

## Consequences

- Common application metrics and family-specific metrics coexist (ADR-026).
- Reproducibility and theoretical planner properties are explicit rather than inferred from planner names.
- PRM-style preprocessing and query cost can be reported both separately and under a declared amortization model.
- No OMPL or ROS dependency is introduced until Sprint V3.5 is activated.
- No MoveIt workspace is introduced until Sprint V3.10 is activated.

## Non-goals

- Implementing any new planner in V3.0.
- Choosing a production Monte Carlo planner mix.
