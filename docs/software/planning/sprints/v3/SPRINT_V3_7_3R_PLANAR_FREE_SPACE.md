# Sprint V3.7 — Planar 3R Free-Space Implementation

**Status:** completed provisional / pre-gate — planar 3R implementation and evidence shipped ahead of V3.6A/V3.6B/V3.6C; residual reconciliation remains drafted until the 2R closeout gate passes
**Reserved work packages:** V3-700–V3-708
**Code authorization:** none (provisional V3-700–V3-706 work already shipped; do not re-authorize until ACTIVE_SPRINT explicitly activates residual reconciliation after V3.6C)
**Depends on:** corrected 2R free-space evidence; dimensional-generalization refactor; reviewed planar 2R visual audit; completed V3.6C closeout; ADR-021–026
**Provisional evidence:** [`results/v3_review/v3_7_3r_free_space/`](../../../../results/v3_review/v3_7_3r_free_space/) (implementation `a65de24`, evidence `5249a5a`; bank `configs/v3/free_space_planar3r_v1.json`)
**Program:** [V3 pre-3R refactor and visual audit](../../V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md)

## Sprint intent

Implement the first higher-dimensional Version 3 robot on the refactored common
architecture: a planar 3R serial arm with three certified scalar transmission
modules and two deliberately separate task families.

1. **Position-only:** Cartesian disk goals in \((x,y)\), leaving one redundant
   degree of freedom and a one-dimensional goal family away from singularities
   and limits.
2. **Full planar pose:** bounded regions in \((x,y,\phi)\in SE(2)\), generally
   reducing to discrete IK families under exact pose constraints.

The sprint tests whether the same physical-state, task, local-motion, objective,
planner, and result contracts survive one additional dimension before spatial
kinematics or collision geometry is introduced.

## Scientific distinction

The task families are separate estimands.

For position-only goals, mechanism-aware cost may change which acceptable
orientation/configuration is preferred:

\[
J^*_{m,\mathrm{position}}
=
\inf_{q_g\in\mathcal G_{xy}}
\left\|g_m^{-1}(q_g)-u_s^{(m)}\right\|_2.
\]

For full pose, orientation removes that free coordinate and provides a control
for effects caused by adding a third planning dimension without redundant goal
selection.

## Task and angle semantics

The full-pose orientation residual is the wrapped distance

\[
d_\phi(\phi,\phi_g)
=
\left|
\operatorname{atan2}
\bigl(\sin(\phi-\phi_g),\cos(\phi-\phi_g)\bigr)
\right|.
\]

A pose-region state satisfies both the Cartesian and angular tolerances. No raw
angle subtraction may cross the \(\pm\pi\) seam.

The start is one exact `PhysicalState`. Numerical attachment residuals remain
planner diagnostics, not task tolerances.

The physical goal predicate remains independent of IK, orientation sampling,
deduplication, or planner representation.

## Represented goal sets

### Full pose

Use deterministic planar 3R IK. For a represented pose sample, compute the wrist
point

\[
x_w=x-L_3\cos\phi,
\qquad
y_w=y-L_3\sin\phi,
\]

solve the corresponding planar 2R elbow families, recover
\(q_3=\operatorname{wrap}(\phi-q_1-q_2)\), lift through each transmission, and
filter limits/residuals.

### Position-only redundancy

Represent the free orientation by a deterministic nested family

\[
\Phi_{K_0}\subset\Phi_{K_1}\subset\cdots,
\]

with fixed phase and doubled resolution, for example \(K\in\{8,16,32\}\).
For each orientation sample, retain all valid elbow families and deduplicate
output states under a frozen tolerance.

Every candidate records:

- Cartesian sample ID;
- orientation sample ID and \(\phi\);
- IK family;
- output state \(q\);
- mechanism inverse residual;
- Cartesian and angular residuals;
- acceptance/rejection reason.

For position-only evidence, label the exact reference over the finite set as

\[
J^*_{\mathrm{position,rep},K}
=
\min_{q_g\in\widehat{\mathcal G}_{xy,K}}
\|u_g-u_s\|_2.
\]

Do not call this the continuous-manifold optimum. Report reference-cost change
as \(K\) increases and freeze the primary \(K\) only after the representation
calibration is reviewed.

## Primary planner parity rule

The primary comparison requires every delivered planner family to consume the
same frozen finite physical goal-state set and ordering. A continuous
`GoalRegion`/`GoalSampleableRegion` adapter may be implemented as a secondary,
separately labeled experiment; its outcomes are not pooled directly with
finite-set suboptimality.

## Mechanism corpus

Use a small diagnostic corpus over one shared Q domain:

1. affine/null control versus itself;
2. nonlinear transmission on joint 1 only;
3. nonlinear transmission on joint 2 only;
4. nonlinear transmission on joint 3 only;
5. nonlinear transmissions on all three joints.

Each nonlinear arm is paired with its span-matched gearbox realization. This
isolates proximal, middle, terminal, and compounded transmission effects before
any mechanism population study.

## Non-goals

- obstacles, self-collision, or world collision;
- 4R/5R partial spatial tasks;
- 6R spatial kinematics;
- MoveIt or URDF integration;
- production Monte Carlo or mechanism-population inference;
- continuous-manifold optimality claims without a solver or bound;
- reopening full-cycle/noninjective mechanisms;
- adding new planner families beyond those already delivered.

## Work packages

### V3-700 — Sprint activation and semantic freeze

Activate only V3.7. Freeze position and pose predicates, wrapped orientation
residual, exact-start semantics, finite-representation reporting, deduplication
tolerance, candidate provenance, primary sign conventions, and separate
position/pose estimands.

### V3-701 — Planar 3R kinematics and robot composition

Add `Planar3R` FK, pose output, link geometry, analytic Jacobian, and consistency
tests. Compose three certified scalar transmission modules through the generic
kinematics/input-domain interfaces delivered by V3.6A. Build shared-Q paired
arms without a second 3R-specific planning architecture.

### V3-702 — Full-pose predicate and deterministic IK

Implement the planar pose region, wrapped angular residual, deterministic wrist
reduction, elbow-family enumeration, limit filtering, transmission lifting, and
candidate provenance.

### V3-703 — Redundant position-goal representation

Implement nested orientation sampling, multi-family IK generation,
deduplication, coverage metrics, and represented-reference convergence across
\(K\). Keep the Cartesian disk predicate independent of the finite
representation.

### V3-704 — Planner integration in three dimensions

Run input/output direct planners, native PRM/RRTConnect, and OMPL PRM/RRTConnect
against the same frozen goal sets. A 26-connected Chebyshev-radius-one lattice
may be used as a small diagnostic only; a dense 3D lattice is not a production
requirement.

### V3-705 — Frozen task and mechanism bank

Create a small external bank with shared physical starts, position-only and
full-pose tasks, short/medium/long descriptors, boundary/singularity proximity,
mechanism-isolation cases, and complete represented-goal provenance.

### V3-706 — Representation and planner calibration

Calibrate orientation resolution, pose sampling, candidate caps, PRM/RRTConnect
budgets, and optional OMPL solve bounds without tuning separately by mechanism.
Freeze a primary finite representation and one seed/repetition contract for the
review artifact.

### V3-707 — 3R evidence artifact

Report, separately for position-only and full-pose tasks:

- common status and task class;
- goal-set coverage and IK/orientation families;
- \(J^*_{\mathrm{pose,rep}}\) or
  \(J^*_{\mathrm{position,rep},K}\);
- planner suboptimality;
- selected orientation and IK family;
- \(L_U,L_Q,L_X\);
- total and phase timings;
- family-specific planner metrics;
- paired \(\Delta J=J_F-J_G\) and absolute compute differences.

### V3-708 — Tests, review, and closeout

Test FK/Jacobian consistency, wrapped-angle behavior, shared starts, deterministic
nested goal sets, candidate deduplication, reference lower bounds, native/OMPL
task-class parity, mechanism-isolation controls, and all pre-V3.7 regressions.

## Exit criteria

1. V3.6A and V3.6B are closed and reviewed; no shared planner code depends on
   `Planar2R` or `robot.branch.certificate`.
2. One `PlanningProblem` contract supports both planar 3R position-only and full
   pose goals.
3. Exact starts are shared in Q and Cartesian pose across each mechanism pair and
   lift to mechanism-specific valid U states.
4. Position-only goals use a deterministic nested represented set rather than one
   arbitrary orientation.
5. Reference-cost convergence across orientation resolution is reported, and
   represented references are not mislabeled as continuous optima.
6. Full-pose goals preserve wrapped orientation tolerance at the angular seam.
7. The primary planner comparison uses the same finite goal states and ordering;
   any continuous goal adapter is reported separately.
8. Mechanism-isolation cases cover null, J1-only, J2-only, J3-only, and all-joint
   nonlinear transmissions.
9. Position-only and full-pose estimands remain separate in every summary.
10. No collision geometry is required for the sprint to pass.
11. V3.8 remains blocked until the 3R implementation and evidence are
    reproducible, reviewed, and accepted as architecture-final.

## Provisional closeout (pre-gate)

A first V3.7 implementation landed before V3.6A/V3.6B under the earlier
ACTIVE_SPRINT authorization of V3-700–V3-706. That work and its review package
are retained as provisional provenance:

- bank: `configs/v3/free_space_planar3r_v1.json`
- artifact: `results/v3_review/v3_7_3r_free_space/`
- commits: implementation `a65de24`, evidence `5249a5a`

Exit criteria 2–3, 6–7 (partial), 9–10 are partially satisfied by that package.
Criteria 1, 4–5, 8, and architecture-final review of 11 remain open residual work
(especially V3-707/V3-708 enrichment and post-refactor reconciliation). Do not
regenerate or rewrite the provisional evidence package while executing V3.6A.

## Residual after V3.6A / V3.6B

After the refactor and visual audit close, ACTIVE_SPRINT may authorize a bounded
V3.7 residual to:

- migrate the provisional 3R robot onto V3.6A generic kinematics / input-domain
  contracts;
- complete nested-\(K\) representation calibration and mechanism-isolation
  corpus items from this revised contract;
- refresh review reporting without silently changing the provisional bank
  semantics unless an explicit corrective contract is written.

Until that residual is activated, V3-700–V3-708 carry no code authorization.
