# ADR-027 — Kinematic transmission geometry as a shared differential layer

- **Status:** Accepted; V4.0 geometry kernel and V4.1 atlas implemented. Later Version 4 columns remain unauthorized until `ACTIVE_SPRINT.md` explicitly activates them
- **Applies to:** Version 4
- **Related:** ADR-001, ADR-014, ADR-021, ADR-022, ADR-024, ADR-026; [V4_PROJECT_PLAN.md](../../V4_PROJECT_PLAN.md)
- **Supersedes:** nothing; frozen Version 1–3 evidence retains its declared contracts

## Context

The repository already represents the physical chain

\[
\mathcal U\xrightarrow{g}\mathcal Q\xrightarrow{f}\mathcal X.
\]

The mechanism interface exposes \(q=g(u)\) and \(J_g=\partial q/\partial u\). The robot and kinematic-model interfaces expose forward kinematics and \(J_f=\partial x/\partial q\). Version 3 uses these maps primarily to define physical states, local motion, actuator-travel objectives, and planner comparisons.

The V3.6C audit also computes the actuator-travel metric expressed on \(Q\), composite actuator-to-task Jacobians, eigenvalues, condition numbers, and metric ellipses. That mathematics currently lives in an audit-specific module. Static wrench analysis, inverse instantaneous kinematics, and potential flow would otherwise reproduce similar matrix composition, rank handling, and transformation logic in separate implementations.

The larger theory requires one tested mathematical source of truth before those columns are added.

## Decision

### 1. Use “kinematic transmission” as the formal physical object

A **kinematic transmission** maps actuator-side coordinates into link-side generalized joint coordinates:

\[
\mathbf q=g(\mathbf u).
\]

A **function generator** describes the mechanism-theory role of generating that input-output relationship. “Inequality mechanism” remains an optional informal phrase for nonuniform actuator-to-output significance.

**Kinematic transmission geometry** is the shared treatment of states, tangent vectors, covectors, metrics, mobility, rank, and composed task-space maps induced by \(g\).

### 2. Preserve the Version 3 physical-state contract

Version 4 continues to use `PhysicalState` as the authoritative physical carrier. The initial study remains on certified monotonic operating branches, so each represented output state has a unique actuator realization. This does not reinterpret Version 1 noninjective-state semantics or authorize full-cycle mechanisms.

### 3. Add a Version 4 differential capability protocol

Do not alter the accepted Version 3 `RobotModel` protocol solely to activate Version 4. Introduce an extension protocol conceptually equivalent to:

```python
@runtime_checkable
class KinematicTransmissionRobotModel(RobotModel, Protocol):
    def jacobian_u_to_q(
        self,
        state: PhysicalState,
    ) -> NDArray[np.float64]:
        """Return J_g = dq/du at the certified physical state."""
```

`OperatingBranchRobotModel` implements this capability through

```python
self.branch.jacobian(state.u)
```

and retains `jacobian_q_to_x(state)` as the source of \(J_f\).

This extension preserves compatibility with legacy V3 fixtures that do not participate in the Version 4 differential studies.

### 4. Introduce a shared geometry kernel

Add a package with pure, independently tested operations:

```text
src/inequality_mechanisms/transmission_geometry/
├── __init__.py
├── errors.py
├── protocols.py
├── differential.py
├── metrics.py
└── snapshot.py
```

The kernel owns the following operations.

#### Tangent pushforward

\[
\dot q=J_g\dot u,
\qquad
\dot x=J_f\dot q,
\qquad
J_{xu}=J_fJ_g.
\]

#### Covector pullback

\[
\tau_u=J_g^\mathsf T\tau_q,
\qquad
\tau_u=J_{xu}^\mathsf TF.
\]

The same operation is used for scalar-potential gradients.

#### Metric pullback and actuator metric on Q

For actuator metric \(W_u\succ0\),

\[
M_Q^{(U)}
=
J_g^{-\mathsf T}W_uJ_g^{-1}.
\]

#### Mobility on Q

\[
B_Q^{(U)}
=
J_gW_u^{-1}J_g^\mathsf T.
\]

When \(J_g\) is square and full rank,

\[
B_Q^{(U)}=\left(M_Q^{(U)}\right)^{-1}.
\]

#### Geometry snapshot

A snapshot records at minimum:

- the certified physical state and task pose;
- \(J_g\), \(J_f\), and \(J_{xu}\);
- singular values and rank reports for all three Jacobians;
- \(W_u\), \(M_Q^{(U)}\), and \(B_Q^{(U)}\) where defined;
- numerical tolerances and operation provenance.

Column-specific software consumes snapshots or the same pure functions. It must not derive alternate meanings for these matrices.

### 5. Make singularity policy explicit

The initial Version 4 actuator metric requires a square, full-rank \(J_g\). When that precondition fails, the kernel raises a typed `DifferentialSingularityError` containing the rank report and operation name.

The kernel must not silently substitute `numpy.linalg.pinv` when computing an inverse-defined metric.

Rank-deficient forward operations remain available where mathematically defined:

- tangent pushforward;
- covector pullback;
- mobility as a positive-semidefinite matrix;
- singular values and rank reports.

A pseudoinverse, damping, truncation, or regularized metric may be added later only through an explicitly named policy with independent tests and provenance.

### 6. Migrate audit mathematics without changing frozen evidence

The fresh V3 audit code may call the Version 4 geometry kernel once V4.0 is activated. It must preserve the existing V3.6C record schema and numerical meaning on regular samples.

No frozen V3.6, V3.6B, V3.6C, or provisional V3.7 result package may be regenerated or overwritten as part of this migration.

### 7. Keep effect columns separate from the geometry kernel

The shared kernel does not itself implement:

- a motion planner;
- inverse-kinematics solvers;
- actuator velocity or torque limits;
- wrench polytopes;
- potential functions or ODE integration;
- Monte Carlo orchestration;
- mechanism ranking.

Those are later Version 4 sprints built on the same geometry.

## Required invariants

The implementation must test the following on analytic gearbox controls and regular four-bar samples.

### Composite derivative

Finite differences of \(f(g(u))\) agree with

\[
J_{xu}=J_fJ_g.
\]

### Metric–mobility duality

For square full-rank \(J_g\),

\[
M_Q^{(U)}B_Q^{(U)}\approx I.
\]

### Virtual power

For arbitrary compatible test vectors,

\[
\tau_u^\mathsf T\dot u
=
\tau_q^\mathsf T\dot q
=
F^\mathsf T\dot x
\]

within the declared numerical tolerance.

### Potential-gradient pullback

Finite differences of a scalar test potential satisfy

\[
\nabla_u(\Phi\circ f\circ g)
\approx
J_{xu}^\mathsf T\nabla_x\Phi.
\]

### Explicit singularity failure

An inverse-defined metric rejects rank-deficient \(J_g\) with the typed error rather than returning a silently regularized matrix.

### Audit regression

Fresh regular-node audit records agree with the pre-extraction implementation within the frozen regression tolerance.

## Consequences

- Planning, inverse instantaneous kinematics, static wrench analysis, and potential flow share one differential and duality implementation.
- The Q-side actuator metric is promoted from an audit-specific quantity to a core geometric object.
- The source of rank loss can be attributed separately to \(J_g\), \(J_f\), and \(J_{xu}\).
- Version 4 can remain on the planar 2R system while testing multiple fundamental consequences of the same physical transmission.
- Applying this ADR does not authorize source changes. `ACTIVE_SPRINT.md` must separately activate Sprint V4.0 after the current Version 3 gate is formally closed.

## Non-goals

- Replacing Version 3 planner architecture.
- Deleting or renumbering the planned Version 3 dimensional roadmap.
- Adding dynamics, compliance, friction, or actuator electrical models.
- Claiming biological equivalence from the planar four-bar example.
- Introducing a scalar score that declares one mechanism globally superior.
