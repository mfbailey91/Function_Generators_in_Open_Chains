# Sprint V4.0 — Kinematic Geometry Core

- **Status:** active; V4-000 through V4-005 and V4-007 authorized; V4-006, V4-008, and V4-009 remain unauthorized
- **Activation dependency:** Version 3.6C gate formally closed and `ACTIVE_SPRINT.md` separately changed
- **Reserved work packages:** V4-000–V4-009
- **Initial mechanism scope:** certified square, full-rank, monotonic gearbox and four-bar branches
- **Initial robot scope:** planar 2R
- **Fresh artifact target:** `results/v4_review/v4_0_kinematic_geometry_core/`

## 1. Sprint purpose

Create one tested source of truth for the kinematic transmission geometry used by all later Version 4 columns.

The sprint extracts mathematics that currently exists partly in mechanism/robot interfaces and partly in V3 audit code:

\[
J_g=\frac{\partial q}{\partial u},
\qquad
J_f=\frac{\partial x}{\partial q},
\qquad
J_{xu}=J_fJ_g,
\]

\[
M_Q^{(U)}=J_g^{-\mathsf T}W_uJ_g^{-1},
\qquad
B_Q^{(U)}=J_gW_u^{-1}J_g^\mathsf T,
\]

and the corresponding tangent pushforward and covector pullback operations.

This sprint is architectural and mathematical. It does not implement inverse-kinematics solvers, wrench polytopes, potential-flow integration, or Monte Carlo.

## 2. Sprint question

> Can planning, differential IK, static wrench, and potential-flow software consume one verified representation of the transmission and robot differential geometry without changing frozen Version 3 evidence?

## 3. Required design outcomes

By sprint close:

1. Version 4-capable robot models expose \(J_g\) through a typed extension protocol.
2. Pure functions implement matrix composition, tangent pushforward, covector pullback, metric, and mobility.
3. Rank and singularity behavior is explicit and serialized.
4. A geometry snapshot joins \(u\), \(q\), \(x\), \(J_g\), \(J_f\), \(J_{xu}\), metrics, mobility, and provenance.
5. The fresh V3 audit path delegates to the new kernel while preserving its current schema and values on regular samples.
6. Analytic, finite-difference, virtual-power, and potential-gradient invariants pass.
7. A small deterministic gearbox/four-bar smoke artifact demonstrates the API without making a comparative performance claim.

## 4. Target source tree

Only the following new package is authorized when V4.0 becomes active:

```text
src/inequality_mechanisms/transmission_geometry/
├── __init__.py
├── errors.py
├── protocols.py
├── differential.py
├── metrics.py
└── snapshot.py
```

Expected existing-file touch points:

```text
src/inequality_mechanisms/adapters/operating_branch_robot.py
src/inequality_mechanisms/audits/metrics.py
src/inequality_mechanisms/audits/__init__.py
src/inequality_mechanisms/__init__.py              # only if public exports require it
scripts/generate_v4_0_geometry_core_smoke.py
```

Expected tests:

```text
tests/transmission_geometry/
├── test_differential.py
├── test_metrics.py
├── test_snapshot.py
├── test_virtual_power.py
└── test_potential_pullback.py

tests/adapters/test_operating_branch_robot_differential.py
tests/audits/test_v3_6c_geometry_kernel_regression.py
```

Do not create later `differential_ik`, `capabilities`, or `flows` packages during this sprint.

## 5. API contract

## 5.1 Version 4 robot capability

Create `protocols.py` with a runtime-checkable extension protocol:

```python
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState


@runtime_checkable
class KinematicTransmissionRobotModel(RobotModel, Protocol):
    def jacobian_u_to_q(
        self,
        state: PhysicalState,
    ) -> NDArray[np.float64]:
        """Return J_g = dq/du at a certified physical state."""
```

`OperatingBranchRobotModel.jacobian_u_to_q(state)` must:

1. validate state dimension;
2. reject inconsistent or out-of-branch states using the existing robot/branch contract;
3. call `branch.jacobian(state.u)`;
4. return a finite `float64` matrix of shape `(dof, input_dim)`;
5. avoid caching until profiling demonstrates need.

Do not add this method to the accepted V3 `RobotModel` protocol in V4.0. The extension protocol is the compatibility boundary.

## 5.2 Errors and rank reports

`errors.py` must define at least:

```python
class TransmissionGeometryError(ValueError):
    """Base class for invalid differential-geometry operations."""


class DifferentialShapeError(TransmissionGeometryError):
    """Raised for incompatible vector or matrix dimensions."""


class DifferentialSingularityError(TransmissionGeometryError):
    """Raised when an inverse-defined operation requires unavailable rank."""
```

The singularity error carries:

- operation name;
- matrix shape;
- numerical rank;
- required rank;
- singular values;
- rank tolerance.

`differential.py` defines:

```python
@dataclass(frozen=True, slots=True)
class RankReport:
    shape: tuple[int, int]
    rank: int
    required_full_rank: int
    singular_values: tuple[float, ...]
    tolerance: float
    full_rank: bool
    condition_number: float | None
```

The rank tolerance must be explicit. A recommended default is the standard scale-aware form

\[
\epsilon_{rank}
=
\epsilon_{machine}\max(m,n)\sigma_{max}
\]

multiplied by a serialized policy factor. The exact policy must be centralized and tested rather than duplicated by callers.

## 5.3 Differential functions

`differential.py` must provide pure functions equivalent to:

```python
def rank_report(matrix, *, tolerance=None) -> RankReport: ...

def composite_jacobian(j_q_to_x, j_u_to_q) -> NDArray[np.float64]: ...

def pushforward_vector(jacobian, vector) -> NDArray[np.float64]: ...

def pullback_covector(jacobian, covector) -> NDArray[np.float64]: ...
```

Required semantics:

- validate finite rank-2 matrices and finite rank-1 vectors;
- never broadcast silently;
- preserve the mathematical order `J_q_to_x @ J_u_to_q`;
- return new `float64` arrays;
- remain independent of `PhysicalState` and robot classes.

## 5.4 Metric and mobility functions

`metrics.py` must provide:

```python
def validate_positive_definite(weight, *, tolerance=None) -> RankReport: ...

def pullback_metric(jacobian, target_metric=None) -> NDArray[np.float64]: ...

def actuator_metric_on_q(
    j_u_to_q,
    actuator_weight=None,
    *,
    rank_tolerance=None,
) -> NDArray[np.float64]: ...

def mobility_on_q(
    j_u_to_q,
    actuator_weight=None,
) -> NDArray[np.float64]: ...

def mobility_on_x(
    j_u_to_x,
    actuator_weight=None,
) -> NDArray[np.float64]: ...
```

### Pullback metric

For a map with differential \(J\) and target metric \(M\),

\[
M_{source}=J^\mathsf TMJ.
\]

If `target_metric` is omitted, use the identity of the target dimension.

### Actuator metric on Q

For square full-rank \(J_g\), solve linear systems rather than explicitly forming `np.linalg.inv(J_g)` where practical:

\[
M_Q^{(U)}=J_g^{-\mathsf T}W_uJ_g^{-1}.
\]

Recommended implementation pattern:

```python
j_inv = np.linalg.solve(j_u_to_q, np.eye(n))
metric = j_inv.T @ actuator_weight @ j_inv
```

Symmetrize roundoff:

```python
metric = 0.5 * (metric + metric.T)
```

A rank-deficient or nonsquare \(J_g\) raises `DifferentialSingularityError`. Do not use a pseudoinverse in this function.

### Mobility

\[
B_Q^{(U)}=J_gW_u^{-1}J_g^\mathsf T.
\]

Use a linear solve for \(W_u^{-1}\). Mobility is allowed to be positive semidefinite when \(J_g\) loses rank.

### Metric–mobility relationship

On square full-rank states, tests require

\[
M_Q^{(U)}B_Q^{(U)}\approx I
\]

and

\[
B_Q^{(U)}M_Q^{(U)}\approx I.
\]

## 5.5 Geometry snapshot

`snapshot.py` defines:

```python
@dataclass(frozen=True, slots=True)
class KinematicGeometrySnapshot:
    u: tuple[float, ...]
    q: tuple[float, ...]
    x: tuple[float, ...]
    j_u_to_q: tuple[tuple[float, ...], ...]
    j_q_to_x: tuple[tuple[float, ...], ...]
    j_u_to_x: tuple[tuple[float, ...], ...]
    rank_u_to_q: RankReport
    rank_q_to_x: RankReport
    rank_u_to_x: RankReport
    actuator_weight: tuple[tuple[float, ...], ...]
    actuator_metric_on_q: tuple[tuple[float, ...], ...] | None
    mobility_on_q: tuple[tuple[float, ...], ...]
    mobility_on_x: tuple[tuple[float, ...], ...]
    metric_status: str
    provenance: Mapping[str, Any]
```

A builder function accepts:

```python
def geometry_snapshot(
    robot: KinematicTransmissionRobotModel,
    state: PhysicalState,
    *,
    actuator_weight=None,
    rank_tolerance=None,
) -> KinematicGeometrySnapshot: ...
```

The builder must:

1. verify `robot.validate_state` under a declared state tolerance;
2. obtain \(J_g\) and \(J_f\) from the robot;
3. compute \(J_{xu}\), rank reports, metric, and mobility;
4. preserve rank-deficient mobility while setting the inverse metric to `None` with a typed status;
5. record implementation/version identifiers and tolerances;
6. avoid embedding planner, task, or solver semantics.

## 5.6 Serialization

Provide explicit `to_dict()` methods or module-level serializers. Do not rely on `dataclasses.asdict` as the long-term schema contract without converting NumPy scalars and arrays deliberately.

Required top-level keys:

```json
{
  "schema_version": "v4.0.geometry_snapshot.v1",
  "u": [],
  "q": [],
  "x": [],
  "jacobians": {},
  "rank_reports": {},
  "metrics": {},
  "provenance": {}
}
```

The record must state whether `actuator_metric_on_q` is available and why it is unavailable when omitted.

## 6. Work packages

## V4-000 — Contract landing and artifact guard

### Implementation

- Land ADR-027, V4 project plan, V4 sprint index, and this sprint plan.
- Do not change `ACTIVE_SPRINT.md` in the planning commit.
- When the sprint is later activated, add a Version 4 artifact guard that permits writes only beneath:

```text
results/v4_review/v4_0_kinematic_geometry_core/
```

- Import the existing frozen Version 3 artifact paths into the guard test.

### Tests

- applying the planning patch changes no source or result file;
- the future V4.0 runner refuses a frozen V3 output directory;
- the fresh V4.0 directory can be created from a clean tree.

### Exit

The sprint has an explicit authorization boundary and cannot overwrite historical evidence.

## V4-001 — Differential capability protocol

### Implementation

- Add `transmission_geometry/protocols.py`.
- Implement `OperatingBranchRobotModel.jacobian_u_to_q`.
- Add public exports only from the new package and adapter module; do not broaden unrelated root exports without need.

### Tests

- runtime protocol recognition;
- identity and fixed gearbox values;
- four-bar branch value matches `branch.jacobian(state.u)`;
- malformed/inconsistent state rejection;
- returned shape and dtype.

### Exit

A V4-capable robot supplies both \(J_g\) and \(J_f\) through documented interfaces.

## V4-002 — Differential algebra

### Implementation

- Add rank reports, composite Jacobian, tangent pushforward, and covector pullback.
- Centralize shape/finiteness validation.

### Tests

- hand-worked rectangular matrices;
- shape mismatch failures;
- nonfinite input failures;
- composition associativity where dimensions permit;
- Planar2R analytic composite values.

### Exit

No later column needs to hand-code `J_f @ J_g` or transpose pullbacks.

## V4-003 — Metric and mobility algebra

### Implementation

- Add positive-definite weight validation.
- Add pullback metric, actuator metric on Q, mobility on Q, and mobility on X.
- Use linear solves and explicit singularity errors.

### Tests

- identity gearbox yields the declared actuator weight on Q;
- diagonal gearbox matches analytic inverse-ratio squares;
- four-bar metric matches the existing regular-node audit calculation;
- metric and mobility are symmetric within tolerance;
- metric–mobility products approximate identity at full rank;
- singular inverse-defined metric raises rather than pseudoinverting.

### Exit

The project has one authoritative implementation of its core metric and mobility identities.

## V4-004 — Geometry snapshots and provenance

### Implementation

- Add snapshot dataclass, builder, and serializer.
- Include rank reports for \(J_g\), \(J_f\), and \(J_{xu}\).
- Record weight, tolerances, robot/mechanism identifiers, and metric status.

### Tests

- deterministic serialization;
- JSON round-trip of the serialized record where a reader is provided;
- rank attribution on crafted transmission and manipulator singularities;
- state and dimensional validation.

### Exit

A single record can feed all four Version 4 columns and visualizations.

## V4-005 — V3 audit kernel migration

### Implementation

Refactor fresh calls in

```text
src/inequality_mechanisms/audits/metrics.py
```

to call the Version 4 geometry functions for:

- \(J_{xu}\);
- `actuator_metric_on_q`;
- eigenvalue/rank-supporting calculations where meanings match.

Preserve:

- `ActuatorMetricOnQRecord`;
- `edge_bundle_to_jsonable` keys;
- regular-sample numerical meaning;
- frozen artifact paths.

Do not rewrite committed V3.6C result files.

### Tests

- golden regular-state values before and after extraction;
- unchanged JSON keys;
- unchanged paired log-scale inputs within tolerance;
- no V4 schema injected into V3 records.

### Exit

The audit no longer owns a second implementation of the shared geometry.

## V4-006 — Differential finite-difference validation

### Implementation

Add reusable finite-difference test helpers for:

\[
J_g\approx\frac{g(u+h e_i)-g(u-h e_i)}{2h},
\]

\[
J_f\approx\frac{f(q+h e_i)-f(q-h e_i)}{2h},
\]

and

\[
J_{xu}\approx\frac{f(g(u+h e_i))-f(g(u-h e_i))}{2h}.
\]

The helper belongs in tests unless a diagnostic API has independent production value.

### Tests

- identity gearbox;
- fixed diagonal gearbox;
- canonical monotonic four-bar pair at endpoints excluded by a declared margin and at interior samples;
- Planar2R at regular and near-manipulator-singular configurations;
- step-size sensitivity bounded and reported in failure messages.

### Exit

Analytic/composed derivatives are validated independently of the implementation path.

## V4-007 — Duality and scalar-potential invariants

### Virtual power test

Generate deterministic compatible vectors and verify

\[
\tau_u=J_g^\mathsf T\tau_q,
\qquad
\tau_q=J_f^\mathsf TF,
\]

\[
\tau_u^\mathsf T\dot u
\approx
\tau_q^\mathsf T\dot q
\approx
F^\mathsf T\dot x.
\]

### Potential pullback test

Use a quadratic Cartesian potential

\[
\Phi_X(x)=\tfrac12(x-x_g)^\mathsf TW_x(x-x_g)
\]

with analytic

\[
\nabla_x\Phi_X=W_x(x-x_g).
\]

Verify finite differences of \(\Phi_X(f(g(u)))\) against

\[
J_{xu}^\mathsf T\nabla_x\Phi_X.
\]

### Exit

The same transpose chain is validated for physical effort and virtual gradients before either application column is implemented.

## V4-008 — Deterministic geometry-core smoke artifact

### Runner

Add:

```text
scripts/generate_v4_0_geometry_core_smoke.py
```

The runner uses:

- the existing canonical planar-2R robot;
- the accepted representative crank-rocker pair;
- the span-matched gearbox control;
- a small shared-\(Q\) grid, recommended `17 x 17`;
- one common actuator weight, initially identity;
- no task outcome or mechanism ranking.

### Outputs

```text
results/v4_review/v4_0_kinematic_geometry_core/
├── manifest.json
├── resolved_config.json
├── geometry_samples.jsonl
├── identity_residuals.json
└── index.html
```

The HTML must show, for both mechanisms on shared scales:

- \(q_i(u_i)\) and \(dq_i/du_i\);
- singular values of \(J_g\), \(J_f\), and \(J_{xu}\);
- eigenvalues of \(M_Q^{(U)}\) and \(B_Q^{(U)}\);
- metric–mobility identity residual;
- maximum finite-difference residual;
- virtual-power residual;
- potential-gradient residual;
- explicit statement: “geometry-core verification; no mechanism performance inference.”

### Exit

A reviewer can inspect the kernel numerically and visually before column-specific implementations begin.

## V4-009 — Closeout and authorization reset

### Review checklist

- all V4.0 tests pass from a clean environment;
- full existing regression suite passes;
- no frozen result digest changes;
- geometry-core smoke artifact is regenerated from the recorded implementation revision;
- no silent pseudoinverse remains in inverse-defined metric code;
- public API and failure behavior match ADR-027;
- V4.1 remains unauthorized.

### Commit separation

Use two commits when evidence is retained:

1. implementation and tests;
2. generated V4.0 smoke evidence and closeout notes.

### Exit

Return `ACTIVE_SPRINT.md` to no authorization or activate V4.1 through a separate reviewed change. V4.0 completion must not automatically authorize later sprints.

## 7. Detailed mathematical acceptance tests

## 7.1 Fixed gearbox control

For

\[
q=Ru+b,
\qquad
R=\operatorname{diag}(r_1,r_2),
\]

require

\[
J_g=R,
\]

\[
M_Q^{(U)}=R^{-\mathsf T}W_uR^{-1},
\]

\[
B_Q^{(U)}=RW_u^{-1}R^\mathsf T.
\]

With \(W_u=I\), the diagonal terms are

\[
M_{ii}=\frac{1}{r_i^2},
\qquad
B_{ii}=r_i^2.
\]

## 7.2 Composite Planar2R derivative

For each regular sample,

\[
J_{xu}^{analytic}=J_f(q)J_g(u)
\]

must agree with central differences of

\[
h(u)=f(g(u)).
\]

Use both absolute and relative tolerances and report the sample, step size, and matrices on failure.

## 7.3 Metric energy identity

For deterministic test displacements \(dq\), compute

\[
du=J_g^{-1}dq.
\]

Require

\[
du^\mathsf TW_u du
\approx
dq^\mathsf TM_Q^{(U)}dq.
\]

## 7.4 Mobility descent identity

For deterministic covectors \(c_q\), define

\[
\dot u=-W_u^{-1}J_g^\mathsf Tc_q.
\]

Require

\[
\dot q=J_g\dot u
\approx
-B_Q^{(U)}c_q.
\]

This is the direct mathematical bridge to the later flow sprint.

## 7.5 Rank attribution

Construct three independent fixtures:

1. full-rank \(J_g\), full-rank \(J_f\), full-rank \(J_{xu}\);
2. rank-deficient \(J_g\) with regular \(J_f\);
3. regular \(J_g\) with rank-deficient \(J_f\).

The snapshot must identify which map loses rank. Composite rank loss may not be attributed automatically to the transmission when only \(J_f\) is singular.

## 8. Commands after activation

The implementation should support a bounded command sequence resembling:

```bash
python -m pytest tests/transmission_geometry -q
python -m pytest tests/adapters/test_operating_branch_robot_differential.py -q
python -m pytest tests/audits/test_v3_6c_geometry_kernel_regression.py -q
python -m pytest -q
python scripts/generate_v4_0_geometry_core_smoke.py \
  --output results/v4_review/v4_0_kinematic_geometry_core
```

Exact command-line options may follow repository conventions, but one documented command must reproduce the smoke package.

## 9. Failure taxonomy

At minimum:

- `invalid_physical_state`;
- `differential_shape_error`;
- `nonfinite_differential`;
- `invalid_actuator_weight`;
- `transmission_rank_deficient`;
- `manipulator_rank_deficient`;
- `composite_rank_deficient`;
- `inverse_metric_unavailable`;
- `finite_difference_validation_failed`;
- `artifact_path_forbidden`.

Failures are results or typed exceptions appropriate to the API layer. Do not convert mathematical failure into `NaN`-filled success records.

## 10. Sprint exclusions

V4.0 must not:

- implement a Jacobian inverse or damped least-squares controller;
- construct velocity or wrench polygons beyond minimal test fixtures;
- integrate a potential-flow ODE;
- add application task banks;
- run mechanism populations or Monte Carlo;
- modify V3 planning estimands;
- activate V3.7, 6R, obstacles, MoveIt, or hardware work;
- overwrite any Version 1–3 evidence.

## 11. Definition of done

Sprint V4.0 is complete only when:

1. ADR-027 is implemented exactly or amended explicitly;
2. the extension protocol supplies \(J_g\) without breaking the accepted V3 `RobotModel` contract;
3. differential, metric, mobility, rank, and snapshot APIs are documented and tested;
4. no inverse-defined metric silently pseudoinverts a singular transmission;
5. composite finite differences pass for gearbox and four-bar controls;
6. virtual-power and potential-gradient identities pass;
7. the fresh V3 audit path uses the shared kernel with schema-preserving regression tests;
8. the smoke artifact is reproducible and explicitly non-inferential;
9. the complete regression suite passes;
10. `ACTIVE_SPRINT.md` does not automatically authorize V4.1.

## 12. Cursor handoff prompt

> Implement only Sprint V4.0 work packages V4-000–V4-009 after confirming `ACTIVE_SPRINT.md` explicitly authorizes them. Preserve all frozen Version 1–3 result packages. Add the `transmission_geometry` package, a V4 extension protocol exposing `jacobian_u_to_q`, explicit rank and singularity handling, pure tangent/covector/metric/mobility functions, and a serializable geometry snapshot. Migrate fresh V3 audit metric calculations to the shared kernel without changing the V3 schema or regenerating frozen evidence. Do not use a silent pseudoinverse for `actuator_metric_on_q`. Validate the implementation with analytic gearbox controls, four-bar and Planar2R finite differences, metric–mobility identities, virtual power, Cartesian potential-gradient pullback, rank-attribution fixtures, and one deterministic non-inferential smoke report under `results/v4_review/v4_0_kinematic_geometry_core/`. Do not implement V4.1 or any differential-IK, wrench, flow, Monte Carlo, 3R, 6R, obstacle, or MoveIt work.
