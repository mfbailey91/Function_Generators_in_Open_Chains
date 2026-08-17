# Sprint V4.3 — Intrinsic Gravity-Free Static-Wrench Capability and Atlas

- **Status:** drafted / blocked; V4-300–V4-309 reserved; unauthorized until V4.2 closes and `ACTIVE_SPRINT.md` names this range
- **Depends on:** frozen V4.2 snapshot banks; accepted V3.6E API; no-authorization predecessor
- **Blocks:** V4.4 velocity / differential IK
- **Reserved work packages:** V4-300–V4-309
- **Artifact target:** `results/v4_review/v4_3_intrinsic_static_wrench/`
- **Kernel rule:** consume V4.0 snapshots already stored by V4.2 and V3.6E `static_wrench_from_snapshot`. Do not recompute \(J_g\), \(J_f\), \(J_{xu}\), or rank tolerances.
- **Cursor guide:** [CURSOR_GUIDE_POST_V4_1_SPAN_WRENCH_PROGRAM.md](../../CURSOR_GUIDE_POST_V4_1_SPAN_WRENCH_PROGRAM.md)

## Sprint purpose

Evaluate the gravity-free actuator torque-box force set on the frozen V4.2 geometry-snapshot corpus. This is the Version 4 intrinsic wrench atlas. It is not a second mathematics kernel and not a gravity-aware application wrench.

## Sprint question

> How does the certified span family redistribute a normalized torque box \(\bar\tau_u=(1,1)\) into planar endpoint force capacity on the same snapshots V4.2 already computed?

## Mathematical contract

\[
\tau_u=J_{xu}^\mathsf T F,\qquad
\mathcal F_x(q)=\{F:-\bar\tau_u\le J_{xu}^\mathsf T F\le\bar\tau_u\}.
\]

Required outputs:

- exact bounded planar endpoint-force polygons at regular states;
- typed unbounded records at rank-deficient states;
- primary scalar heatmap \(\rho_{\mathrm{iso}}\) (shipped field `isotropic_radius`);
- Cartesian \(x\), Cartesian \(y\), radial, and tangential directional-capacity heatmaps;
- sparse shape-normalized polygon glyphs and selected true-scale details;
- separate rank attribution for \(J_g\), \(J_f\), and \(J_{xu}\);
- shared paired scales for four-bar and gearbox comparisons.

Gravity, payload, dynamics, friction, compliance, structural limits, and contact remain absent.

Point methods and biological-range documentation at existing [STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md](../../../architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md) and [BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md](../../../research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md). Do not claim new biology.

## Work packages

## V4-300 — Artifact guard and schema

V4.3 writers may write only `results/v4_review/v4_3_intrinsic_static_wrench/`. Refuse V4.0, V4.1, V4.2 overwrite, all `v3_review` packages, and gravity/payload keys.

## V4-301 — Consume V4.2 snapshots and V3.6E

Join V4.2 rows by stable snapshot IDs and config/registry digests. Call `static_wrench_from_snapshot`. Do not rebuild Jacobians.

## V4-302 — Exact polygons

Regular-state torque-box polygons from V3.6E. Verify vertices against \(\tau_u=J_{xu}^\mathsf T F\). No silent clipping.

## V4-303 — Scalar field

Primary heatmap is `isotropic_radius` / \(\rho_{\mathrm{iso}}\). Mask nonregular states. Shared paired four-bar/gearbox scales.

## V4-304 — Directional fields

`positive_x`, `positive_y`, `radial`, `tangential` via `wrench_directions.py`. Typed origin/undefined failures.

## V4-305 — Unbounded and rank attribution

Reuse snapshot rank reports. Statuses remain the V3.6E set (`regular`, `near_singular`, `rank_deficient`, `unbounded_ideal_direction`, …). Do not fabricate a bounded inverse.

## V4-306 — HTML atlas

Scalar-first index; directional selector; sparse polygons; selected true-scale details; rank masks. Link to V4.2; do not edit the V4.2 package.

## V4-307 — Methods and biological pointers

Emit `methods.md` and a biological-trace pointer that cite the existing method note and literature trace. No new biological constants.

## V4-308 — Tests

Analytic polygon fixtures still pass through the V3.6E API. V4.2 and V4.1 checksums unchanged. Gravity keys rejected. 17-case evaluation complete. Finite values are never manufactured by pseudoinverse.

## V4-309 — Closeout and authorization reset

Write a closeout note. Return `ACTIVE_SPRINT.md` to no authorization. Do not auto-start V4.4.

## Compact Cursor prompt

> Implement only Sprint V4.3 work packages V4-300–V4-309 after V4.2 is closed and `ACTIVE_SPRINT.md` authorizes them. Consume frozen V4.2 snapshot IDs and the V3.6E static-wrench API. Do not recompute \(J_g\), \(J_f\), or \(J_{xu}\). Write only `results/v4_review/v4_3_intrinsic_static_wrench/`. Do not overwrite V4.1 or V4.2. Do not add gravity, payload, or force-aware planning.
