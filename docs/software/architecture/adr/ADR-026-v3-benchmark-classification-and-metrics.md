# ADR-026 — Version 3 benchmark classification and metrics contract

**Status:** Proposed  
**Applies to:** Version 3  
**Related:** ADR-017, ADR-021, ADR-023, ADR-025; Sprint V3.0 V3-007  
**Supersedes:** nothing for frozen Version 2 reports

## Context

Version 2 Monte Carlo reporting leaned on node expansions and relative log ratios. Free-space tasks that are already satisfied or directly connectable were pooled with tasks requiring global search. The centered Q-spanner is scientifically useful but is not a representative Cartesian application-task distribution.

## Decision

### Classify before benchmarking

Every task is classified without using the comparative planner outcome:

1. **already satisfied** — start lies in the goal region;
2. **direct/local feasible** — a declared direct connector is valid under the scene and constraints;
3. **global planning required** — direct connectors fail;
4. **invalid/unreachable** — task cannot be represented or reached.

Do not pool these regimes into one undifferentiated expansion statistic.

### Pre-search difficulty descriptors

Record Cartesian start–goal separation, direct input- and output-space distances, goal tolerance, goal-set measure or represented count, IK-family count, boundary proximity, obstacle/constraint class, and direct-connector status. Planner outcome must not be the sole difficulty classifier.

### Common application metrics

Every planner returns, where meaningful: status and failure taxonomy; wall time; selected goal state; objective cost; actuator, output, and Cartesian path lengths; state/motion/collision check counts; direct-connector availability; final task residual; reproducibility metadata.

### Planner-specific metrics (namespaced)

Examples: graph expansions/generated/reopened/queue ops/heuristic error; roadmap samples/vertices/edges/query attachment; tree samples/extensions/NN ops; trajectory-optimization iterations; industrial generation time. Store under `PlanningResult.planner_metrics` with a planner-family namespace.

### Paired effect metrics

Retain relative effects such as

\[
\Delta\log N=\log\frac{N_F+1}{N_G+1},
\]

but never report them alone. Also report

\[
\Delta N=N_F-N_G,\qquad \Delta t=t_F-t_G,\qquad \Delta J=J_F-J_G.
\]

Report effects by task class and size/difficulty strata before any overall task-distribution mean.

### Diagnostic Q-spanner

Preserve centered and other designed \(\mathcal Q\)-space probes as a separate diagnostic suite with a separate experiment identity and estimand. Allowed: expose metric orientation, local gain effects, planner/grid artifacts, and hypotheses. Not allowed: present a Q-spanner mean as the representative robot-task effect, or merge Q-spanner and Cartesian application estimands.

### Schema draft direction

Version 3 result records follow `PlanningResult` in ADR-021, with `task_class` required and planner metrics namespaced. A detailed JSON/YAML schema is authored when Sprint V3.1 implements serialization; this ADR freezes the semantic contract only.

## Consequences

- Benchmark runners must classify tasks before comparing planners or mechanisms.
- Frozen Version 2 reports remain valid under their declared metrics; they are not retrofitted.
- Production Monte Carlo remains blocked until task, planner, scene, local-motion, metric, and statistical contracts are stable.

## Non-goals

- Implementing the benchmark schema or statistics stack in V3.0.
- Re-analyzing V2.10/V2.11 under the new classification without a separate diagnostic study.
