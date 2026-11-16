# Active sprint

**Current focus:** Sprint V4.3 is **active**: intrinsic gravity-free static-wrench capability and atlas on frozen corrected V4.2B snapshots.

**Code authorization:** V4-300–V4-309 only.

**Activated:** 2026-11-15 by the explicit request to activate V4.3 and start its sprint plan. Baseline: `027d5af34e72ac33767a9538b17fb96588a2bc60` (main, V4.2D closeout merged). This activation records the implementation contract; it does not mark any V4.3 work package completed.

**Start here:** [Sprint V4.3](sprints/v4/SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md) and its [Cursor implementation roadmap](sprints/v4/V4_3_CURSOR_IMPLEMENTATION_ROADMAP.md). Start with V4-300 (schema and artifact guard), then V4-301 (frozen snapshot ingestion). Implement and validate one bounded slice at a time. Retained generation follows passing implementation checks and a clean source commit; closeout follows artifact verification and evidence review.

**Scientific contract:** planar 2R, normalized actuator torque box `(1, 1)`, exact force sets through the accepted V3.6E `static_wrench_from_snapshot` API. Consume the stored V4.2B mounted-coordinate Jacobians and rank reports. Keep the four-bar, span-matched gearbox, and identity controls at identical physical Q/X states within each case. Preserve all 17 cases and the `boundary_stress_only` label for 175-degree axes.

**Input:** `results/v4_review/v4_2b_span_controlled_corrective_closeout/` only for the span-family snapshot corpus. V4.2/V4.2A remain historical. Source identities and expected counts are locked in the sprint. V4.2C/V4.2D closeouts establish the completed planning column; V4.3 does not rerun those planners.

**Artifact writes:** V4.3 may write only under `results/v4_review/v4_3_intrinsic_static_wrench/`, after its dedicated output guard is implemented. Never overwrite a completed run or any predecessor package. Test fixtures use isolated temporary roots. Runtime guard implementation is V4-300 work, not a claim made by this activation.

**Completed:** V2.0–V2.12 smoke/calibration (production held); V3.0–V3.5; V3.6 corrective 2R free-space evidence; **Sprint V3.6A**; **Sprint V3.6B**; **Sprint V3.6C**; **Sprint V4.0** kinematic geometry core; **Sprint V4.1** planar-2R intrinsic geometry atlas; **Sprint V3.6D** canonical span corpus; **Sprint V3.6E** gravity-free static wrench core; **Sprint V3.6F** static wrench atlas; **Sprint V4.2** span-controlled geometry atlas (historical); **Sprint V4.2A** span-controlled visual planning audit (historical); **Sprint V4.2B** mounted-coordinate corrective closeout; **Sprint V4.2C** OMPL planner-geometry portfolio; **V4.2C-R** frozen-data report clarification; **Sprint V4.2D** optimality-reference and gearbox-control report.

**Frozen evidence:** all committed packages under `results/v3_review/`; V4.0 `v4_0_kinematic_geometry_core`; V4.1 `v4_1_planar2r_geometry_atlas`; V4.2 `v4_2_span_controlled_geometry_atlas`; V4.2A `v4_2a_span_controlled_visual_audit`; V4.2B `v4_2b_span_controlled_corrective_closeout`; V4.2C `v4_2c_ompl_planner_portfolio`; V4.2C-R `v4_2c_r_frozen_data_report`; and V4.2D `v4_2d_optimality_reference_report`. Do not mutate or regenerate these packages.

**Roadmap:** active V4.3 intrinsic wrench → separately activated V4.4 velocity / differential IK → V4.5 potential fields / continuous flow. V4-309 must close V4.3 and return this file to no code authorization; V4.4 does not auto-start. Residual V3.7 remains separately drafted / blocked.

**Held:** V4.4+, Version 2 Cartesian production inference, obstacles, MoveIt, 3R/6R, residual V3.7, V3.8+, V4.0A kernel rewrites, production V4-006, gravity/payload/dynamics/friction/compliance/contact/structural-limit models, force-aware planning, mechanism resynthesis, certificate retuning, native OMPL clones, and deferred items (`V3-DEFER-001`, `V3-DEFER-002`).

**Governing references:** [V4 project plan](../V4_PROJECT_PLAN.md), [V4 sprint index](sprints/v4/README.md), [ADR-027](../architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md), [ADR-028](../architecture/adr/ADR-028-gravity-free-static-wrench.md), [ADR-029](../architecture/adr/ADR-029-mounted-output-coordinate.md), [V4.2B canonical evidence review](../architecture/notes/V4_2B_CANONICAL_EVIDENCE_REVIEW.md), and [V4.2D closeout](../architecture/notes/V4_2D_OPTIMALITY_REFERENCE_CLOSEOUT.md). Historical closeout notes retain their original no-auto-activation statements.
