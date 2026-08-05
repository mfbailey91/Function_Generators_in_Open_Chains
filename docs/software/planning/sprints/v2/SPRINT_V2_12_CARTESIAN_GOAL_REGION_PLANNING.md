# Sprint V2.12 — Cartesian Goal-Region Planning

**Status:** active — bounded smoke implementation; production held
**Experiment:** Experiment B
**Robot:** planar 2R
**Task:** known start state to position-only Cartesian goal region
**Primary solvers:** Dijkstra and A* (`input_euclidean_goal_set`)
**Primary objective:** actuator travel

This sprint is active for the bounded kickoff scope below. It does not authorize
population production, sequential stopping, or paper-level Experiment B claims.
Those remain blocked on calibration decisions and crossed-statistics implementation.

## Sprint intent

Implement the first representative task-space planning experiment after the
centered \(\mathcal Q\)-space mechanism probes.

The sprint changes the query semantics from:

\[
\mathbf q_s\rightarrow\mathbf q_g
\]

to:

\[
\mathbf q_s\rightarrow\mathcal R_X(\mathbf x_g).
\]

It does not change the certified-branch mechanism contract, shared
uniform-\(\mathcal Q\) graph, span-matched gearbox control, or actuator-travel
objective.

## Why this sprint exists

Experiment A was a controlled metric probe. A 2R motion planner is more commonly
asked to navigate to a Cartesian position than to one arbitrarily preselected
joint configuration.

Experiment B lets the graph choose any valid final posture satisfying the
position task. It therefore evaluates how the mechanism-induced actuator metric
affects:

- reachability under a fixed external task distribution;
- selected IK posture;
- path cost;
- node expansions;
- actuator, output, and Cartesian path geometry.

## Activation decision

The bounded implementation is activated because:

1. Experiment A semantics are documented for both V2.10 Dijkstra and V2.11 A*;
2. [ADR-019](../../../architecture/adr/ADR-019-v2-cartesian-task-domain.md) accepts the fixed smoke/calibration domain;
3. [ADR-020](../../../architecture/adr/ADR-020-v2-goal-set-search.md) accepts generalized goal-set search and the actuator-distance A* heuristic;
4. crossed statistics is explicitly not needed to validate one-pair smoke correctness and remains a production gate;
5. the shared-\(\mathcal Q\) pair invariant remains green;
6. exact start query support from V2.6 remains reproducible;
7. the Experiment B protocol is reviewed.

The current V2.7 3R gate is unchanged by this sprint existing as held work.
Activating V2.12 does not by itself authorize 3R.

## Non-goals

This sprint does not include:

- obstacles or collision checking;
- dynamics or torque limits;
- continuous local trajectory optimization;
- Cartesian orientation;
- 3R or 6R;
- full-cycle/noninjective mechanisms;
- adaptive graph refinement;
- tuning the external task distribution to favor either mechanism;
- a task-location atlas for the Experiment A diagonal observation;
- copying V2.10 pair-nested sequential precision unchanged;
- implementing against the proposed ADR placeholders.

## Resolved design gates and remaining production gate

### V2B-P1 — Cartesian-domain ADR — accepted

ADR-019 freezes `planar2r_left_workcell_v1`, area-uniform sampling, attachment radii, and separation for smoke/calibration.

### V2B-P2 — Goal-set search ADR — accepted

ADR-020 freezes the generalized solver API, deterministic termination, Dijkstra oracle, and `input_euclidean_goal_set` A*.

### V2B-P3 — Crossed statistical design — production gate

Before any population campaign, accept and implement uncertainty/stopping logic that preserves both mechanism and task dependence. Smoke rows are correctness evidence only.

## Implementation work packages

### V2B-001 — Uniform-area Cartesian sampler

Implement the accepted ADR-019 sampler with seed reproducibility, rejection
taxonomy, and spatial-uniformity diagnostics.

### V2B-002 — Start IK enumeration and frozen selection

Enumerate analytic families, filter by certified shared \(\mathcal Q\)-box and
discrete graph representatives, select one frozen policy, and record exclusions.

### V2B-003 — Goal-set search implementation

Extend the existing solver stack per ADR-020. Single-goal queries remain a
special case. No second planner stack.

### V2B-004 — Cartesian goal-region builder

Build \(V_G\) from graph-node Cartesian coordinates and the frozen goal radius.
Prove pair identity of membership.

### V2B-005 — Goal-radius and resolution calibration

Write decision JSON. Production refuses a missing radius or resolution decision.

### V2B-006 — Fixed external task-bank export

Export an immutable Cartesian bank before production search. Do not regenerate
in place.

### V2B-007 — Result schema and failure taxonomy

Typed outcomes must include start unreachable, empty goal region, disconnected
goal region, paired-query validity, search failure, and solved. Unreachable
tasks remain visible outcomes.

### V2B-008 — Crossed statistical analysis

Implement the accepted design from V2B-P3.

### V2B-009 — Search and path diagnostics

Render domain, start, goal disk, goal nodes, selected posture, \(\mathcal Q\)
and \(\mathcal U\) views, Cartesian path, and paired comparison.

### V2B-010 — Pair-local workspace control

Optional secondary bank with a separate experiment ID. Never merge into the
external-domain primary mean.

### V2B-011 — Production orchestration

Reuse V2.10 operational lessons (generate-only bank, hardware preflight, shard
lifecycle) only after the clustering unit is updated for the crossed design.
Production compares separately configured Dijkstra and A* campaigns only after the crossed design is accepted.

## Activated kickoff scope

The first patch is complete only when it provides:

1. backward-compatible single-goal plus explicit/predicate goal-set search;
2. `input_euclidean_goal_set` objective resolution and admissibility tests;
3. analytic planar-2R IK for task diagnostics;
4. the fixed annular-sector task sampler and deterministic graph attachment;
5. pair-identity hard gates for start and goal sets;
6. one versioned smoke config and CLI that run both Dijkstra and A*;
7. immutable task, trial, failure, config, and manifest outputs;
8. Dijkstra/A* optimal-cost agreement as a run-time hard gate.

The kickoff does **not** implement population-bank orchestration, crossed
bootstrap confidence intervals, sequential precision, calibration decisions,
or an evidence canvas.

## Primary outputs

1. accepted ADR-019 domain and frozen external Cartesian task bank;
2. accepted ADR-020 goal-set search;
3. goal-radius and resolution decisions;
4. paired reachability table;
5. conditional expansion-effect estimate;
6. actuator/output/Cartesian path metrics;
7. selected-goal posture distribution;
8. crossed task/mechanism uncertainty;
9. HTML evidence canvas;
10. explicit comparison to Experiment A without combining estimands.

## Scientific interpretation rules

Allowed:

> Under the frozen external Cartesian position-task distribution, the
> transmission changed paired reachability-conditioned search effort by ...

Allowed:

> The mechanism changed which valid goal posture was cheapest under the
> actuator-travel objective.

Not allowed:

> Four-bars reduce planning complexity in general.

Not allowed:

> The Experiment A medium diagonal proves a diagonal Cartesian advantage.

## Exit criteria

Sprint V2.12 is complete when:

1. goal-set Dijkstra passes oracle tests;
2. the fixed external Cartesian domain is normative;
3. Cartesian sampling is uniform under the declared area measure;
4. start IK selection is frozen, paired, and fully recorded;
5. four-bar and gearbox goal-node sets match exactly within every pair;
6. goal radius and graph resolution have accepted decisions;
7. unreachable and disconnected tasks remain visible outcomes;
8. crossed uncertainty is implemented;
9. a smoke run and production-ready dry run reproduce from one command;
10. the report distinguishes Experiment A and Experiment B estimands.

## Handoff

After Experiment B review:

1. decide whether any Experiment A diagnostic atlas is still worth running
   given that A* already failed the first persistence check;
2. retain the current V2.7 gate unless a later explicit decision changes it;
3. retain 6R \(SE(3)\) pose planning as a later research-program extension.
