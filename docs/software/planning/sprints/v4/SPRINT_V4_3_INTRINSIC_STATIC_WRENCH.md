# Sprint V4.3 — Intrinsic Gravity-Free Static-Wrench Capability and Atlas

- **Status:** drafted / blocked; V4-300–V4-309 reserved; unauthorized until V4.2B closes and `ACTIVE_SPRINT.md` separately names this range
- **Depends on:** frozen corrected V4.2B snapshot banks; accepted V3.6E API; no-authorization predecessor
- **Historical inputs not consumed:** V4.2 and V4.2A remain retained diagnostic evidence but are not the downstream snapshot source
- **Blocks:** V4.4 velocity / differential IK
- **Reserved work packages:** V4-300–V4-309
- **Artifact target:** `results/v4_review/v4_3_intrinsic_static_wrench/`
- **Kernel rule:** consume V4.0 snapshots already stored by V4.2B and V3.6E `static_wrench_from_snapshot`. Do not recompute \(J_g\), \(J_f\), \(J_{xu}\), or rank tolerances.
- **Corrective dependency:** [Sprint V4.2B](SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md) and [ADR-029](../../../architecture/adr/ADR-029-mounted-output-coordinate.md)

## Sprint purpose

Evaluate the gravity-free actuator torque-box force set on the frozen, mounted-coordinate V4.2B geometry-snapshot corpus. This is the Version 4 intrinsic wrench atlas. It is not a second mathematics kernel and not a gravity-aware application wrench.

## Sprint question

> How does the certified span family redistribute a normalized torque box \(\bar\tau_u=(1,1)\) into planar endpoint force capacity on the same corrected mounted-Q snapshots V4.2B computed?

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

V4.3 writers may write only `results/v4_review/v4_3_intrinsic_static_wrench/`. Refuse V4.0, V4.1, V4.2, V4.2A, V4.2B overwrite, all `v3_review` packages, and gravity/payload keys.

## V4-301 — Consume V4.2B snapshots and V3.6E

Join V4.2B rows by stable snapshot IDs and config/registry/source digests. Require mounted-coordinate provenance from ADR-029. Call `static_wrench_from_snapshot`. Do not rebuild Jacobians and do not fall back to historical V4.2 or V4.2A rows.

## V4-302 — Exact polygons

Regular-state torque-box polygons from V3.6E. Verify vertices against \(\tau_u=J_{xu}^\mathsf T F\). No silent clipping.

## V4-303 — Scalar field

Primary heatmap is `isotropic_radius` / \(\rho_{\mathrm{iso}}\). Mask nonregular states. Shared paired four-bar/gearbox scales.

## V4-304 — Directional fields

`positive_x`, `positive_y`, `radial`, `tangential` via `wrench_directions.py`. Typed origin/undefined failures.

## V4-305 — Unbounded and rank attribution

Reuse snapshot rank reports. Statuses remain the V3.6E set (`regular`, `near_singular`, `rank_deficient`, `unbounded_ideal_direction`, …). Do not fabricate a bounded inverse.

## V4-306 — HTML atlas

Scalar-first index; directional selector; sparse polygons; selected true-scale details; rank masks. Link to V4.2B as the snapshot source and to V4.2/V4.2A only as historical provenance. Do not edit predecessor packages.

## V4-307 — Methods and biological pointers

Emit `methods.md` and a biological-trace pointer that cite the existing method note and literature trace. No new biological constants.

## V4-308 — Tests

Analytic polygon fixtures still pass through the V3.6E API. V4.0/V4.1/V4.2/V4.2A/V4.2B checksums unchanged. Gravity keys rejected. Corrected 17-case evaluation complete. Mounted-coordinate provenance is required. Finite values are never manufactured by pseudoinverse.

## V4-309 — Closeout and authorization reset

Write a closeout note. Return `ACTIVE_SPRINT.md` to no authorization. Do not auto-start V4.4.

## Compact Cursor prompt

> Implement only Sprint V4.3 work packages V4-300–V4-309 after V4.2B closes and `ACTIVE_SPRINT.md` separately authorizes them. Consume frozen corrected V4.2B mounted-coordinate snapshot IDs and the V3.6E static-wrench API. Do not recompute \(J_g\), \(J_f\), or \(J_{xu}\), and do not fall back to historical V4.2/V4.2A rows. Write only `results/v4_review/v4_3_intrinsic_static_wrench/`. Do not overwrite any predecessor package. Do not add gravity, payload, or force-aware planning.
