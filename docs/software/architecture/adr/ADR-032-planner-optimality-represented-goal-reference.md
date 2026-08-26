# ADR-032 — Planner Optimality Must Be Measured Against the Exact Represented-Goal Reference

**Status:** Accepted; implemented by Sprint V4.2D
**Applies to:** Version 4 Column A planning diagnostics; V4.2C portfolio interpretation
**Related:** ADR-021, ADR-023, ADR-024, ADR-026, ADR-029, ADR-030, ADR-031
**Supersedes:** nothing

## Context

Sprint V4.2C established that OMPL families can consume the mounted, mechanism-aware planning problem while preserving authoritative actuator state, exact starts, input-linear local motion, and actuator-travel cost. The retained Stage C report plots absolute planner cost. That is not yet an optimality statement.

An optimality gap requires a reference \(J^*_m\) on the same finite represented goal set the planner actually received. Two retained packages look similar and are not interchangeable:

- V4.2B planning-audit `input_linear` rows minimize over a broader Cartesian-disk representation (center plus boundary octants).
- The V4.2C worker uses `CartesianDiskGoalGenerator`, which generates planar-2R IK lifts of the disk **center only**. Typical candidate keys are `disk_center::elbow_down` and `disk_center::elbow_up`.

Joining V4.2C planner costs to \(J^*_{B,m}\) would mix representations. A planner that reached every V4.2C center-IK candidate could still look suboptimal against a cheaper V4.2B boundary preimage that was never in the V4.2C goal set.

## Decision

### 1. The V4.2C optimum is the min valid direct cost on the actual center-IK set

For mechanism \(m\) on one frozen case/task:

\[
J^*_{C,m}
=
\min_{g\in G_{C,m}}
\|u_g-u_s\|_2,
\]

where \(G_{C,m}\) is the finite set produced by `CartesianDiskGoalGenerator` on the reconstructed V4.2C `PlanningProblem`, evaluated with `InputLinearMotion` and `ActuatorTravelObjective`. Already-satisfied queries have \(J^*_{C,m}=0\).

Candidate identity is the stable key `<goal_sample_id>::<ik_family>`.

### 2. Historical \(J^*_{B,m}\) is a representation-sensitivity control only

\(J^*_{B,m}\) is the unique V4.2B `input_linear` cost for the same (case, task, mechanism). It may appear in \(\Delta J_{\mathrm{representation},m}=J^*_{C,m}-J^*_{B,m}\). It is never the V4.2C convergence denominator, never the relative-gap scale, and never the time-to-tolerance threshold.

### 3. Planner gaps are measured against \(J^*_{C,m}\)

Absolute and relative gaps, cost ratios, time-to-tolerance, and within-tolerance fractions use \(J^*_{C,m}\). A reconstructed exact planner cost strictly below \(J^*_{C,m}-\tau\) is a generation failure, not a clipped negative gap.

### 4. Mechanism pairing is index-matched, not common-random-number

Equal OMPL seeds across four-bar and gearbox do not prove identical sample sequences. Paired \(\Delta J_C^*\) and \(\Delta\epsilon^{\mathrm{rel}}\) are descriptive index-matched contrasts.

## Consequences

V4.2D reconstructs \(J^*_{C,m}\) without importing or solving OMPL, joins every Stage C row to that reference, and reports mechanism-optimum change separately from planner discoverability. Frozen V4.2B and V4.2C packages remain byte-identical.

## Test consequences

Required tests include:

- 100 primary center-IK reference rows on the frozen audit matrix;
- candidate generator ID and candidate-count agreement with retained V4.2C metadata;
- unique V4.2B `input_linear` rows per (case, task, mechanism);
- non-negative gaps beyond numerical \(\tau\);
- relative metrics null on already-satisfied / zero-reference tasks;
- final-gap decomposition identity;
- immutable predecessor artifact digests.

## Rejected alternatives

### Use V4.2B `input_linear` cost as the V4.2C optimum

Rejected because the finite goal sets differ. That comparison is representation sensitivity, not planner suboptimality.

### Treat the cheaper of \(J^*_B\) and \(J^*_C\) as the denominator

Rejected because a planner cannot be scored against a candidate it was never given.

### Infer checkpoint goal identity from the final selected candidate

Rejected. V4.2C checkpoints do not retain the selected goal at each time. Final-gap decomposition is the only certified split into goal-selection regret and path inefficiency.
