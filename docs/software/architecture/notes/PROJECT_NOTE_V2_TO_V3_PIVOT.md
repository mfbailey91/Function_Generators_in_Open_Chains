# Project Note — What the Version 2 Monte Carlo Revealed

**Status:** retained project rationale, not an evidence claim

## Summary

The Version 2 Monte Carlo campaign was valuable because it scaled a controlled formulation far enough to expose which assumptions were part of the mechanism effect and which assumptions belonged to the experiment architecture.

The campaign should be preserved, not erased. Its results apply to the declared centered-Q task suite, graph topology, objective, and solver. They should not be generalized silently to robot motion planning as a whole.

## Formulation findings to preserve

### Fixed Q-space task lengths

The centered normalized-Q probes intentionally controlled approximate task location while varying displacement scale and direction. They were useful mechanism and solver probes, but they are not a representative Cartesian robot-task distribution.

The stronger Dijkstra `medium_diagonal` effect did not persist under A*, so it remains a low-confidence clue about the interaction among task chord, graph topology, metric, and solver.

### Start tolerance

A robot has a known physical start state. `start_tolerance` arose from attaching a sampled Cartesian start to a discrete graph. It must not remain a task-semantic parameter.

Version 3 uses an exact start state. Graph and roadmap planners attach it through validated query connections; tree planners use it as the root.

### Four-connected motion

The historical graph permitted one coordinate to change at a time. This introduced staircase paths, grid-orientation effects, and tie degeneracy.

Version 3 treats local motion as a continuous object and begins lattice validation with simultaneous joint motion. Four-connectivity remains a historical and diagnostic ablation.

### Free-space planner necessity

Many free-space tasks are already satisfied or directly connectable. They may not require global search in an application.

Version 3 classifies tasks before benchmarking and separates direct/local tasks from tasks requiring global planning.

### Benchmark scaling

A relative log expansion ratio does not express absolute computational importance. Similar ratios can describe one saved expansion or thousands of saved expansions.

Version 3 reports relative and absolute effects, task-size strata, solve time, objective cost, and planner-family-specific metrics.

### Q-spanner value

The designed Q-spanner remains useful as a secondary diagnostic. It can reveal metric directionality, graph artifacts, and local mechanism effects that an application task distribution averages away.

It must retain a separate experiment identity and estimand.

## Decision

Pause production scaling and build Version 3 as a planner-agnostic mechanism-aware motion-planning framework.
