# Project Note — Validate Dimension Before Obstacles

**Status:** accepted roadmap rationale  
**Applies to:** Version 3 after Sprint V3.6  
**Related:** ADR-021–026; `V3_PROJECT_PLAN.md`; Sprint V3.6

## Decision

Do not introduce collision geometry or obstacle-routing experiments immediately after the 2R free-space benchmark.

The Version 3 validation sequence is:

\[
\boxed{
2R\ \text{free space}
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

from planner representation, local motion, validity, objectives, and benchmark policy.

The 2R study validates that separation in the simplest nontrivial case. The next architectural risk is dimensional/task generalization, not collision checking.

If obstacles were added before higher-DOF free-space validation, a failed experiment could be caused by any combination of:

- serial forward kinematics or Jacobians;
- \(U\leftrightarrow Q\) state consistency;
- goal-region or IK representation;
- redundant-goal handling;
- local-motion semantics;
- nearest-neighbor or sampling behavior in higher dimension;
- collision checking;
- or actual obstacle topology.

The revised sequence removes the collision variables while 3R and 6R are brought onto the common V3 contract.

## Validation ladder

### 2R planar position — Sprint V3.6

Establish the controlled free-space baseline:

- same physical start across mechanisms;
- same represented Cartesian goal region;
- direct actuator-space reference;
- deterministic and stochastic planner parity;
- paired mechanism effects and planner suboptimality.

### 3R planar — Sprint V3.7

Introduce two new semantics while retaining visualization and analytical tractability:

1. position-only goals \((x,y)\), which are redundant for a 3R arm;
2. full planar pose goals \((x,y,\phi)\in SE(2)\).

This is the first explicit test of a goal manifold / redundant IK family under the V3 planner-independent contract.

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
