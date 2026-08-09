# Project Note — Validate Architecture and Dimension Before Obstacles

**Status:** accepted roadmap rationale; amended with pre-3R gates
**Applies to:** Version 3 after Sprint V3.6
**Related:** ADR-021–026; `V3_PROJECT_PLAN.md`; Sprint V3.6; `V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md`

## Decision

Do not introduce collision geometry or obstacle-routing experiments immediately after the 2R free-space benchmark without first removing known dimensionality seams and reviewing the current 2R implementation visually. A provisional planar 3R package may already exist; treat architecture-final 3R acceptance as blocked until the pre-3R gates close.

The Version 3 validation sequence is:

\[
\boxed{
2R\ \text{free-space evidence}
\rightarrow
\text{dimension-general refactor}
\rightarrow
2R\ \text{visual audit}
\rightarrow
3R\ \text{planar free space}
\rightarrow
6R\ \text{spatial free space}
\rightarrow
\text{cross-DOF closeout}
\rightarrow
\text{collision/obstacles}
}
\]

Spatial 4R/5R partial-task studies remain accepted follow-on work but are not a gate before 6R.

## Why

Version 3 separates

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X
\]

from planner representation, local motion, validity, objectives, instrumentation, and benchmark policy.

The corrected 2R study validates the scientific comparison in the simplest nontrivial case. Before adding a third robot coordinate, the shared implementation must stop reaching through concrete `Planar2R` and operating-branch details. Before leaving the visually legible 2R case, the project should also expose how Q nodes, mechanism-specific U states, Cartesian embeddings, local edge metrics, and planner traces are actually produced.

If 3R or obstacles were added immediately, a failed experiment could be caused by any combination of:

- a residual planar-2R dependency in shared code;
- robot-owned versus branch-owned sampling bounds;
- serial forward kinematics or Jacobians;
- \(U\leftrightarrow Q\) state consistency;
- goal-region or IK representation;
- redundant-goal handling;
- local-motion and integrated-edge semantics;
- nearest-neighbor or sampling behavior in higher dimension;
- collision checking;
- or actual obstacle topology.

The revised sequence removes those confounds in stages.

## Validation ladder

### 2R planar position evidence — Sprint V3.6

Establish the controlled free-space baseline:

- same physical start across mechanisms;
- same represented Cartesian goal region;
- direct actuator-space reference;
- deterministic and stochastic planner parity;
- paired mechanism effects and planner suboptimality.

### Dimensional-generalization refactor — Sprint V3.6A

Remove concrete implementation seams without changing frozen results:

- generic kinematic-model delegation;
- robot-owned input domains;
- kinematics-specific goal generators outside `core.goals`;
- shared U/Q/X trajectory metrics;
- synthetic three-dimensional architecture fixture.

This is a behavior-preserving refactor, not a 3R result.

### Planar 2R visual audit — Sprint V3.6B

Generate a small offline HTML audit over ten frozen corrected V3.6 tasks. Organize the artifact by trial and show:

- four-bar and span-matched gearbox transmission maps;
- shared Q graphs and mechanism-specific U embeddings;
- Cartesian graph/path embeddings;
- integrated \(w_U\), \(w_Q\), and \(w_X\) edge fields;
- Dijkstra/A*, roadmap, and tree exploration traces;
- direct, path, and planner metrics;
- the actual code/dataflow architecture.

This is implementation introspection, not inferential evidence. Any discrepancy becomes a V3.7 blocker.

### 3R planar — Sprint V3.7

Introduce two new semantics on the refactored architecture while retaining visualization and analytical tractability:

1. position-only goals \((x,y)\), which are redundant for a 3R arm;
2. full planar pose goals \((x,y,\phi)\in SE(2)\).

This is the first explicit test of a redundant goal family and wrapped planar orientation under the V3 planner-independent contract.

### 6R spatial — Sprint V3.8

Move to a standard spatial serial manipulator without URDF, self-collision, or world obstacles.

Use:

- exact physical starts;
- spatial position regions;
- full \(SE(3)\) pose regions;
- deterministic/frozen numerical IK candidate generation;
- direct and sampling-based planners appropriate to six dimensions.

A dense tensor lattice is not a required 6R baseline.

### Cross-DOF closeout — Sprint V3.9

No new collision features.

Freeze evidence showing that the same contracts survive:

- 2R planar position;
- 3R planar position and pose;
- 6R spatial position and pose.

This is an architecture-validation milestone, not a claim that raw timings or planner events are directly comparable across dimensions.

## What obstacles add later

After the cross-DOF gate, collision work becomes one new variable rather than several.

Sprint V3.10 adds collision-scene capability. Sprint V3.11 then asks the genuinely different question:

> When the direct connector is blocked and nonlocal routing is actually required, how does the mechanism-induced actuator metric affect route choice, feasibility, and planner effort?

## 4R/5R status

Underactuated and partial-task spatial robots remain valuable because they stress task predicates that do not occupy all six dimensions of \(SE(3)\). They are deferred under `V3-DEFER-002`, not abandoned.

They should be activated when the research question is specifically about:

- pointing;
- orientation cones;
- constrained planes;
- remote-center constraints;
- partial poses;
- or underactuated task manifolds.

They are not required to prove that the V3 architecture scales from planar to a conventional 6R spatial manipulator.
