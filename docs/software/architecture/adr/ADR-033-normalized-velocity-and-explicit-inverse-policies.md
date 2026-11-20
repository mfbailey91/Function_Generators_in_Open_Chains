# ADR-033 — Normalized velocity capability and explicit inverse policies

- **Status:** accepted for Sprint V4.4, authorized by the owner on 2026-11-20
- **Applies to:** V4 Column B, initially planar 2R instantaneous capability and differential IK
- **Related:** ADR-027 shared geometry; ADR-028 static wrench; ADR-029 mounted coordinates
- **Implementation:** `metrics/velocity.py`; retained-source smoke in `experiments/v4/intrinsic_velocity.py`
- **Scope boundary:** this decision does not supply a trajectory, timestep, feedback law, domain-boundary rule, or hardware actuator model

## Context

The same retained transmission geometry must support a velocity comparison after the static-wrench comparison. The scientific question is how the mapping changes directional capability and the actuator motion needed for the same Cartesian motion. No motor selection or physical speed rating is available or needed for this first comparison.

An unbounded actuator-rate domain would give no finite capability boundary for a full-rank map. We therefore need a common comparison domain. A normalized unit box is a declared mathematical convention. Results may also report unconstrained inverse demand, so that the effect of this convention remains visible.

## Decision

### 1. Consume the geometry snapshot

Use the stored mounted-coordinate snapshot and its `J_g`, `J_f`, `J_xu`, state, rank reports, and provenance. Validate dimensions, finiteness, composition, and inherited-rank consistency. Do not rebuild mechanisms, retune rank thresholds, shift joint coordinates, or use a default pseudoinverse cutoff to redefine physical rank. The first API accepts finite planar 2-by-2 snapshots.

### 2. Forward capability uses a declared finite rate box

For positive coordinate-rate limits `b = (b1, b2)`, define

\[
\mathcal V_u=\{\dot u: |\dot u_i|\le b_i\},\qquad
\mathcal V_x=J_{xu}\mathcal V_u.
\]

The initial retained-source smoke uses `b = (1, 1)`. Store all actuator corners and their images through the **raw stored Jacobian**. The velocity set is bounded at every rank. Rank loss makes the set lower dimensional; it never means unbounded velocity capability.

For a unit direction `d`, distinguish two quantities:

\[
h_{\mathcal V_x}(d)=\sum_i b_i\left|(J_{xu}^{T}d)_i\right|,
\qquad
r_{\mathcal V_x}(d)=\max\{s\ge0:sd\in\mathcal V_x\}.
\]

Support is a maximum projection and need not be achieved on the requested ray. Ray speed requires velocity in that exact direction. For an invertible map,

\[
r_{\mathcal V_x}(d)=\frac{1}{\max_i |(J_{xu}^{-1}d)_i|/b_i}.
\]

Keep both values and label them. Normalize supplied nonzero directions. A zero or unavailable radial direction is explicitly undefined, rather than silently changed to another direction.

### 3. Numerical rank and raw geometry are separate records

A snapshot classified numerically rank deficient can retain a tiny nonzero singular value in its raw matrix. Raw corner images and support retain that information. Degenerate ray calculations use the explicitly named inherited-rank SVD model, with its Jacobian and corner images serialized separately. Off-range rays have zero speed in that model; the rank-zero model has zero speed in every defined direction. The full-dimensional isotropic speed is zero at inherited rank loss.

No truncation may silently replace the stored map. Plots must identify which representation they show. Physical status (`regular`, `near_singular`, bounded rank deficient, or bounded zero rank) remains separate from solver success.

### 4. Inverse policy is a required argument

Each request chooses one policy:

| Policy | Meaning | Rank behavior |
| --- | --- | --- |
| `exact` | Solve `J_xu * u_dot = v_requested` | Requires inherited full rank; singular requests are explicitly unavailable |
| `minimum_norm` | Minimum weighted actuator norm among least-squares solutions | Use the explicitly recorded inherited-rank physical map; no independent cutoff |
| `damped_least_squares` | Minimize `||J_xu * u_dot - v_requested||^2 + lambda^2 * u_dot^T W * u_dot` | Positive finite damping; preserve physical rank even when the solve is regularized |

`W` must be finite, symmetric, and positive definite through the shared geometry validator. Weighted minimum norm first selects the inherited physical subspace of the raw map, then solves weighted constrained minimization within that subspace. Weighting cannot select a new physical rank or subspace. DLS uses the raw map with explicit positive damping and actuator whitening. Its normal equations are

\[
(J_{xu}^{T}J_{xu}+\lambda^2 W)\dot u=J_{xu}^{T}v_{requested}.
\]

The first smoke uses `W = I` and `lambda = 0.05` in the declared normalized coordinate convention. This is an illustrative, reproducible policy setting, not a tuned optimum. A later tracking study must compare documented damping settings on a declared task bank.

### 5. Rate enforcement is explicit

`report_only` retains unconstrained requested rates and reports their coordinatewise utilization and feasibility. `uniform_scale` multiplies the entire actuator-rate vector by

\[
\alpha=\min\left(1,\frac{1}{\max_i |\dot u_i|/b_i}\right),
\]

with `alpha = 1` for the zero command. This is a transparent speed reduction. It is not independent coordinate clipping or a claim to solve a constrained least-squares optimization.

Serialize the requested and commanded rates, target and achieved Cartesian velocities, residuals before and after scaling, utilization, feasibility, applied scale, physical status, solver status, damping, weight, and solver map. The achieved velocity always uses the raw stored `J_xu`; regularization must not hide the actual residual.

### 6. Retain a paired, reproducible first smoke

Use frozen V4.2B physical samples, source locks, and all three existing arms: four-bar, span-matched gearbox, and identity on shared Q. The first smoke has four cases, five grid locations per case, and 60 records. It tests instantaneous behavior, including singular samples. It does not estimate tracking error, certify a full atlas, or rank mechanisms globally.

Every production entry point uses the same fresh-root, clean-source preflight. The only production output is `results/v4_review/v4_4_velocity_ik_smoke/`. Never delete and recreate an occupied output tree. Test destinations must be explicitly isolated and cannot resolve into canonical retained evidence. Strict finite JSON, exact source identity, a complete file inventory, and independent algebra checks are required before retention.

## Acceptance and consequences

Analytic controls cover identity, anisotropic and signed maps, rank one, rank zero, nonidentity SPD weight, invalid inputs, DLS normal equations, box support versus ray speed, rate scaling, and instantaneous power duality. Retained-source checks verify pairing, source locks, all row counts, stored-matrix corner images, achieved-velocity residuals, rate utilization, finite transport, and overwrite refusal.

The first implementation opens the next project step without changing the force-set model or any frozen evidence. V4.4 remains active until its full intrinsic atlas, task/integration contract, tracking comparisons, review, and closeout gates are complete. V4.5 continuous flow requires separate activation.
