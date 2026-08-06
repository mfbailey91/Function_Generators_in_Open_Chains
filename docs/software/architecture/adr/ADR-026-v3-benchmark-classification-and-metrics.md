# ADR-026 — Version 3 benchmark classification and metrics contract

**Status:** Accepted  
**Applies to:** Version 3  
**Related:** ADR-017, ADR-021, ADR-023, ADR-025; Sprint V3.0 V3-007  
**Supersedes:** nothing for frozen Version 2 reports

## Context

Version 2 Monte Carlo reporting leaned on node expansions and relative log ratios. Free-space tasks that are already satisfied or directly connectable were pooled with tasks requiring global search. The centered Q-spanner is scientifically useful but is not a representative Cartesian application-task distribution.

## Decision

### Classify before benchmarking

Every mechanism-task instance is classified before comparative planner outcomes are known:

1. **already satisfied** — the exact start satisfies the goal predicate;
2. **direct/local feasible** — at least one declared direct connector is valid under the scene, constraints, and named connector policy;
3. **direct connector unavailable** — none of the declared direct connectors succeeds; this is the pre-search stratum that **invites** nonlocal (lattice, roadmap, tree, OMPL, …) planners under the declared connector policy;
4. **invalid/unrepresentable** — the start, goal, scene, physical state, or required planner representation cannot be constructed under the declared contract;
5. **certifiably unreachable** — only when an analytical proof, exhaustive finite search, disconnected-component certificate, or equivalent reachability certificate is available.

A planner timeout, sample exhaustion, or failure to find a path is a post-search outcome such as `unsolved` or `timeout`; it is not evidence of unreachability.

“Direct connector unavailable” replaces the informal label “global planning required.” It is relative to the declared connector policy and does not claim that every conceivable local motion family would fail. Sprint V3.2 and later runners must use this stratum name when routing tasks to nonlocal planners so wording does not drift back to an unqualified “global” claim.

Do not pool these regimes into one undifferentiated expansion or runtime statistic.

### Paired mechanism classification

Classification is recorded per mechanism because direct feasibility may itself be a mechanism effect. Paired studies additionally use strata such as:

- `both_direct`;
- `fourbar_only_direct`;
- `gearbox_only_direct`;
- `neither_direct`;
- paired invalid or certified-unreachable combinations.

Do not force two mechanisms into one task class when their physical local-motion outcomes differ.

### Pre-search difficulty descriptors

Record Cartesian start–goal separation, direct input- and output-space distances, goal tolerance, goal-region descriptor, finite represented goal count when applicable, IK-family count, boundary proximity, obstacle/constraint class, declared direct-connector policy, and per-mechanism direct-connector status. Planner outcome must not be the sole difficulty classifier.

### Common application metrics

Every planner returns, where meaningful:

- status and failure taxonomy;
- `setup_time`;
- `preprocessing_time`;
- `query_time`;
- `postprocessing_time`;
- `total_wall_time`;
- selected goal state;
- objective cost;
- actuator, output, and Cartesian path lengths;
- state/motion/collision check counts;
- direct-connector policy and availability;
- final task residual;
- reproducibility metadata.

For reusable structures, report both standalone total cost and amortized query cost under a declared query count and task distribution.

### Planner-specific metrics (namespaced)

Examples: graph expansions/generated/reopened/queue ops/heuristic error; roadmap samples/vertices/edges/query attachment; tree samples/extensions/NN ops; trajectory-optimization iterations; industrial generation time. Store under `PlanningResult.planner_metrics` with a planner-family namespace.

Planner-family events are not interchangeable. A graph expansion, roadmap sample, tree extension, and trajectory-optimization iteration may be compared within a stable instrumentation contract, but must not be presented as one cross-family “search effort” count.

### Paired effect metrics

Retain relative effects such as

\[
\Delta\log N=\log\frac{N_F+1}{N_G+1},
\]

when \(N\) has the same planner-family meaning in both paired arms, but never report it alone. Also report

\[
\Delta N=N_F-N_G,\qquad
\Delta t=t_F-t_G,\qquad
\Delta J=J_F-J_G.
\]

Report effects by per-mechanism task class, paired direct-feasibility stratum, and size/difficulty strata before any overall task-distribution mean.

### Diagnostic Q-spanner

Preserve centered and other designed \(\mathcal Q\)-space probes as a separate diagnostic suite with a separate experiment identity and estimand. Allowed: expose metric orientation, local gain effects, planner/grid artifacts, and hypotheses. Not allowed: present a Q-spanner mean as the representative robot-task effect, or merge Q-spanner and Cartesian application estimands.

### Schema draft direction

Version 3 result records follow `PlanningResult` in ADR-021, with per-mechanism `task_class`, post-search `status`, timing decomposition, and planner metrics namespaced. A detailed JSON/YAML schema is authored when Sprint V3.1 implements serialization; this ADR freezes the semantic contract only.

## Consequences

- Benchmark runners classify mechanism-task instances before comparing planner outcomes.
- Unreachability is claimed only with a recorded certificate.
- Direct-feasibility asymmetry is retained as a mechanism result rather than averaged away.
- Cross-family planner metrics remain namespaced and semantically distinct.
- Frozen Version 2 reports remain valid under their declared metrics; they are not retrofitted.
- Production Monte Carlo remains blocked until task, planner, scene, local-motion, metric, and statistical contracts are stable.

## Non-goals

- Implementing the benchmark schema or statistics stack in V3.0.
- Re-analyzing V2.10/V2.11 under the new classification without a separate diagnostic study.
