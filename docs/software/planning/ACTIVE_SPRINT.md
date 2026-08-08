# Active sprint

**Current focus:** [Sprint V3.6A — Dimensional-Generalization Refactor](sprints/v3/SPRINT_V3_6A_DIMENSIONAL_GENERALIZATION_REFACTOR.md).

**Code authorization:** V3-610–V3-617 only (generic kinematics protocol, robot-owned input domains, kinematics-specific goal generators outside `core.goals`, shared U/Q/X trajectory metrics, opt-in planner traces, compatibility adapters, regression suite). No planar-3R feature work beyond preserving the provisional V3.7 implementation, no V3.6B audit HTML, no obstacles, MoveIt, 6R, production Monte Carlo, or `V3-DEFER-001` / `V3-DEFER-002` closure.

**Completed:** V2.0–V2.12 smoke/calibration (production held); V3.0–V3.5; V3.6 corrective 2R free-space evidence ([`results/v3_review/v3_6_free_space_v2/`](../../results/v3_review/v3_6_free_space_v2/); v1 pilot superseded at [`results/v3_review/v3_6_free_space/`](../../results/v3_review/v3_6_free_space/)); **provisional** Sprint V3.7 planar 3R free-space implementation and evidence ([`results/v3_review/v3_7_3r_free_space/`](../../results/v3_review/v3_7_3r_free_space/); implementation `a65de24`, evidence `5249a5a`) landed ahead of the pre-3R gates and is **not** architecture-final until V3.6A and V3.6B close and residual V3.7 reconciliation is reviewed.

**Frozen evidence:** [V2 evidence freeze](../experiments/reports/V2_EVIDENCE_FREEZE.md). V3.5 review snapshot: [`results/v3_review/v3_5_closeout/`](../../results/v3_review/v3_5_closeout/). V3.6 corrected closeout: [`results/v3_review/v3_6_free_space_v2/`](../../results/v3_review/v3_6_free_space_v2/). Provisional V3.7: [`results/v3_review/v3_7_3r_free_space/`](../../results/v3_review/v3_7_3r_free_space/).

**Roadmap:** V3.6A (active) → V3.6B (drafted) → revised V3.7 residual / post-refactor reconciliation (drafted) → V3.8–V3.13 (drafted; no code authorization). See the [pre-3R program plan](V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md) and [V3 dimensional-roadmap note](../architecture/notes/V3_ROADMAP_DIMENSION_BEFORE_OBSTACLES.md).

**Held:** Version 2 Cartesian production inference, Version 2.7 3R (V2 path), new Monte Carlo campaigns, obstacles, MoveIt, 6R implementation, Sprint V3.6B, Sprint V3.8+, re-authorization of V3-700–V3-708, and deferred items (`V3-DEFER-001`, `V3-DEFER-002`) until separately activated.
