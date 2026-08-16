# V4.0 kinematic geometry core closeout

**Disposition:** accepted (V4-009)
**Kernel / smoke implementation revision:** `3d096e30145fbe09b62a9a4b61c3e79db6e52ac6`
**Smoke package:** [`results/v4_review/v4_0_kinematic_geometry_core/`](../../../../results/v4_review/v4_0_kinematic_geometry_core/)
**Work packages closed:** V4-000 through V4-005, V4-007, V4-008, and V4-009
**Not implemented:** V4-006 reusable Jacobian finite-difference helpers (deferred; smoke and duality tests use local stencils)

## Review conclusion

Sprint V4.0 extracted one tested kinematic-transmission kernel:

\[
J_g=\partial q/\partial u,\qquad
J_f=\partial x/\partial q,\qquad
J_{xu}=J_f J_g,
\]

\[
M_Q^{(U)}=J_g^{-\mathsf T}W_u J_g^{-1},\qquad
B_Q^{(U)}=J_g W_u^{-1} J_g^{\mathsf T}.
\]

The kernel lives in `inequality_mechanisms.transmission_geometry`. Fresh V3 audit metric calculations call it without changing the V3.6C record schema. Frozen Version 1–3 result packages were not regenerated.

## Checklist

| Item | Result |
| --- | --- |
| V4.0 tests from a clean environment | `tests/transmission_geometry`, `tests/adapters/test_operating_branch_robot_differential.py`, `tests/audits/test_v3_6c_geometry_kernel_regression.py`, `tests/v4` |
| Full regression suite | 1611 passed, 26 skipped |
| Frozen V3 review digests | lockfile `tests/v4/data/frozen_v3_review_digests.json`; `tests/v4/test_v4_009_closeout.py` |
| Geometry-core smoke regenerated from recorded implementation revision | `results/v4_review/v4_0_kinematic_geometry_core/`; non-inferential HTML |
| No silent `pinv` in inverse-defined metric code | kernel package and `audits/metrics.py` |
| Public API and failure behavior match ADR-027 | protocol extension, typed singularity, `artifact_path_forbidden` |
| V4.1 remains unauthorized | `ACTIVE_SPRINT.md` has no code authorization; V4.1 stays drafted / blocked |

## Explicitly out of scope

V4.0 did not implement differential IK, wrench polytopes, potential-flow ODEs, Monte Carlo, 3R, 6R, obstacles, or MoveIt. Deferred hardening (not V4.1 kernel rewrites unless an atlas failure blocks the sprint):

- `geometry_snapshot(..., state_tolerance=)` is only partially honored because `OperatingBranchRobotModel.jacobian_u_to_q` re-validates with hard-coded `1e-9`. Preferred later fix: pass the declared tolerance through the differential query.
- `pullback_metric` does not SPD-check a user-provided `target_metric`. Tighten that contract before Sprint V4.4; do not rename the operation to a bilinear-form pullback.
- V4-006 reusable Jacobian finite-difference helpers remain deferred as a production API. Independent \(J_g\), \(J_f\), and \(J_{xu}\) checks belong under V4.1 tests (V4-107).

## Authorization

`ACTIVE_SPRINT.md` returns to **no code authorization**. Activating Sprint V4.1 (`V4-100`–`V4-108`) or residual V3.7 requires a separate reviewed change. V4.0 completion does not authorize later sprints.
