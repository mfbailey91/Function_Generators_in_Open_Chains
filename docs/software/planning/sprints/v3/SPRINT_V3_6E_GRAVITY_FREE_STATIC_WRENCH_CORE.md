# Sprint V3.6E — Gravity-Free Static Wrench Core

**Status:** completed; V3-660–V3-669 closed
**Reserved work packages:** V3-660–V3-669
**Depends on:** accepted V3.6D artifact, no-authorization state, and the closed V4.0 `transmission_geometry` kernel
**Blocks:** V3.6F and architecture-final V3.7 activation
**Validation target:** `results/v3_review/v3_6e_static_wrench_core/`
**Kernel rule:** consume V4.0 snapshots / Jacobians / rank / virtual-power identities. Do not rederive \(J_{xu}\) in a V3 audit module. This sprint is not V4.3.

## Sprint question

> Can the existing mechanism and arm Jacobians produce a correct, typed, gravity-free static force-capability model before visualization choices are allowed to shape the mathematics?

## Mathematical contract

For

\[
q=g(u),\qquad x=f(q),
\]

define

\[
J_g(u)=\frac{\partial q}{\partial u},\qquad
J_f(q)=\frac{\partial x}{\partial q},\qquad
J_{xu}(u)=J_f(g(u))J_g(u).
\]

Virtual work gives

\[
\tau_u=J_{xu}(u)^\mathsf T w.
\]

With symmetric actuator limits

\[
-\bar\tau_u\le\tau_u\le\bar\tau_u,
\]

the exact normalized force set is

\[
\mathcal W(u)=
\{w:\left|J_{xu}(u)^\mathsf T w\right|\le\bar\tau_u\}.
\]

For the current planar 2R endpoint task,

\[
w=[F_x,F_y]^\mathsf T.
\]

Do not add an end-effector moment coordinate in this sprint.

## Work packages

### V3-660 — Static-wrench ADR and scope guard

Record the model as **intrinsic gravity-free kinematic geometry**. The ADR must state that gravity, payload, dynamics, losses, compliance, and structural capacity are excluded and that adding gravity later creates a different model and result lineage.

Add schema validation that rejects unsupported fields such as `gravity_vector`, `payload_mass`, or `gravity_compensation` for this solver family.

### V3-661 — Data model and typed statuses

Recommended records:

```python
class WrenchStateStatus(Enum):
    REGULAR = "regular"
    NEAR_SINGULAR = "near_singular"
    RANK_DEFICIENT = "rank_deficient"
    UNBOUNDED_IDEAL_DIRECTION = "unbounded_ideal_direction"
    INVALID_MECHANISM_STATE = "invalid_mechanism_state"
    UNDEFINED_TASK_DIRECTION = "undefined_task_direction"

@dataclass(frozen=True)
class StaticWrenchCapability2D:
    q: NDArray
    u: NDArray
    J_g: NDArray
    J_f: NDArray
    J_xu: NDArray
    torque_limits: NDArray
    hrep_A: NDArray
    hrep_b: NDArray
    vertices: NDArray | None
    isotropic_radius: float
    directional_capacity: Mapping[str, float]
    rank: int
    singular_values: NDArray
    status: WrenchStateStatus
```

Computed values remain unclipped. Visualization caps are separate metadata.

### V3-662 — Composite Jacobian service

Implement one dimension-checked path from physical state to `J_g`, `J_f`, and `J_xu`. Reuse the certified branch and existing kinematic model. Test array shapes, coordinate conventions, and the identity

\[
\dot x=J_{xu}\dot u.
\]

### V3-663 — Exact 2D force-polytope solver

Let

\[
A=J_{xu}^\mathsf T.
\]

Return the H-representation

\[
-\bar\tau\le Aw\le\bar\tau.
\]

When `A` is nonsingular, compute the four vertices by mapping actuator-torque-box corners:

\[
w=A^{-1}s,\qquad
s_i\in\{-\bar\tau_i,+\bar\tau_i\}.
\]

Sort vertices consistently for plotting. For rank-deficient states, do not invent a closed polygon; return the H-representation and typed unbounded-direction information.

### V3-664 — Scalar and directional capacity

For a unit direction `d`, implement

\[
\alpha^*(d)=
\min_{i:\,|a_i^\mathsf Td|>\epsilon}
\frac{\bar\tau_i}{|a_i^\mathsf Td|},
\]

with infinity when all denominators vanish.

Implement the largest centered Euclidean disk radius

\[
r_{\mathrm{iso}}
=
\min_{i:\,\|a_i\|>\epsilon}
\frac{\bar\tau_i}{\|a_i\|_2}.
\]

Initial named directions:

- Cartesian `+x` and `+y`;
- radial from base to endpoint;
- tangential about the base.

Radial/tangential directions are typed undefined when the endpoint is too close to the base origin.

### V3-665 — Singularity and near-toggle semantics

Distinguish at least:

- arm-Jacobian rank loss;
- mechanism low gain / near rocker reversal;
- composite rank loss;
- finite but extreme ideal capability;
- mathematically unbounded ideal directions.

Never translate “unbounded in the rigid ideal model” into “infinitely strong.” Store separate margins and status masks. Thresholds are configuration values frozen before atlas inspection.

### V3-666 — Gearbox/four-bar normalized parity

For each span case, use the same:

- physical Q grid;
- link lengths;
- normalized actuator torque limits, initially `[1,1]`;
- task directions;
- numerical tolerances.

This isolates the mechanism map. Add mechanism-only joint-torque amplification diagnostics so the full wrench field can be decomposed into transmission and serial-arm effects.

### V3-667 — Vectorized grid evaluation and caching

Add batched evaluation over shared Q grids. Cache by:

- mechanism-registry hash;
- case ID;
- Q-grid specification;
- torque-limit vector;
- method schema version.

Cached results must be numerically identical to scalar evaluation and may not bypass state validity or status logic.

### V3-668 — Mathematical test suite

Required tests:

1. random virtual-work identity;
2. identity and constant-gear analytic fixtures;
3. four-bar `J_g` finite-difference agreement;
4. every regular polygon vertex saturates valid torque-box constraints;
5. all polygon points satisfy the H-representation;
6. directional capacity agrees with polygon-ray intersection or a reference linear program;
7. isotropic radius agrees with brute-force angular sampling within tolerance;
8. linear scaling with actuator torque limits;
9. rotational equivariance of Cartesian force directions;
10. typed rank-deficient and unbounded-direction behavior;
11. no solver/config gravity field accepted;
12. scalar and batched outputs agree.

### V3-669 — API closeout and validation artifact

Write analytic fixture tables, random-test summaries, singularity fixtures, schema/version metadata, and numerical tolerances to the E artifact. Return to no authorization; do not auto-activate V3.6F.

## Proposed source targets

```text
src/inequality_mechanisms/
├── metrics/
│   ├── static_wrench.py
│   └── wrench_directions.py
├── kinematics/
│   └── composite_jacobian.py
└── audits/
    └── static_wrench_validation.py

scripts/export_v3_6e_static_wrench_core.py
tests/v3/test_v3_6e_static_wrench_core.py
```

## Exit criteria

1. The math API is independent of HTML/Matplotlib.
2. Exact polygons, scalar capacities, and directional capacities agree with independent references.
3. Singular and unbounded ideal cases are typed rather than silently clipped.
4. Gravity and payload are absent from accepted schema and code paths.
5. All five span outcomes supported by V3.6D evaluate deterministically.
6. Validation artifact is generated from a clean revision.
7. Repository returns to no authorization.
