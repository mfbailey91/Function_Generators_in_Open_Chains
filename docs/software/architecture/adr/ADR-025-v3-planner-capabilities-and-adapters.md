# ADR-025 — Version 3 planner capability and adapter contract

**Status:** Proposed  
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
    multi_query: bool
    optimizing: bool
    supports_goal_region: bool
    supports_path_constraints: bool
    reports_graph_exploration: bool
    supports_exact_start: bool
```

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

Native and external adapters consume `PlanningProblem` and return `PlanningResult`. Planner-specific fields belong in capabilities, configuration, and `planner_metrics`, never in the problem definition.

## Consequences

- Common application metrics and family-specific metrics coexist (ADR-026).
- No OMPL or ROS dependency is introduced until Sprint V3.5 is activated.
- No MoveIt workspace is introduced until Sprint V3.10 is activated.

## Non-goals

- Implementing any new planner in V3.0.
- Choosing a production Monte Carlo planner mix.
