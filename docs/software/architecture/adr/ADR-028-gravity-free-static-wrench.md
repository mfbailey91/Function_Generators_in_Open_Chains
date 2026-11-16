# ADR-028 — Gravity-free static wrench from kinematic geometry

- **Status:** Accepted for V3.6E–F and active Sprint V4.3. V4.3 is the Version 4 **intrinsic** atlas consuming this API on frozen corrected V4.2B mounted-coordinate snapshots; velocity capability remains V4.4. Exact source authorization comes only from `ACTIVE_SPRINT.md`.
- **Applies to:** Version 3.6E/F planar 2R program; consumes Version 4.0 geometry kernel; Version 4.3, separately activated on 2026-11-15
- **Related:** ADR-027; [STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md](../notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md); [V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md](../../planning/V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md)
- **Supersedes:** nothing; frozen V3.6/V4.0/V4.1 evidence is unchanged

## Context

Planning, velocity, wrench, and flow columns all need \(J_g\), \(J_f\), and \(J_{xu}\). V4.0 already owns those maps. This ADR records the **gravity-free static** force set induced by a symmetric actuator torque box, so later gravity-aware models cannot be introduced as a hidden boolean.

## Decision

1. The model is intrinsic kinematic geometry plus ideal virtual work:
   \(\tau_u = J_{xu}^\mathsf T w\) with \(w=[F_x,F_y]^\mathsf T\) for planar 2R.
2. Gravity, payload, inertia, friction, compliance, and structural limits are **outside the model**. Adding them requires a new ADR, schema name, and result lineage.
3. Exact torque-box polygons are authoritative. Ellipsoids are labeled summaries only.
4. Rank-deficient or unbounded ideal directions are typed statuses, never clipped into a fake polygon.
5. Implementation consumes V4.0 `geometry_snapshot` / `composite_jacobian` / `rank_report`. It does not rederive Jacobians. V3.6E owns the force-set mathematics. Sprint V4.3 consumes that API on frozen corrected V4.2B mounted-coordinate snapshots and must not fork a second kernel. Historical V4.2/V4.2A snapshots are excluded by [ADR-029](ADR-029-mounted-output-coordinate.md). Stored rank reports and numerical policies remain authoritative; the existing API's composite-map consistency check is allowed.

## Consequences

- Config and solver schemas reject `gravity_vector`, `payload_mass`, and `gravity_compensation`.
- V3.6E writes only `results/v3_review/v3_6e_static_wrench_core/`.
- Normalized \(\bar\tau_u=[1,1]\) isolates transmission geometry from actuator scaling.
