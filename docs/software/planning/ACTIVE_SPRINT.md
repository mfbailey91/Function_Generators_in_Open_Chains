# Active sprint

**Current focus:** none.

**Code authorization:** none. Do not implement V4.2+, V4.3, residual V3.7, obstacles, MoveIt, 6R, gravity-aware wrench, or force-aware planning until `ACTIVE_SPRINT.md` names an exact work-package range.

**Completed:** V2.0–V2.12 smoke/calibration (production held); V3.0–V3.5; V3.6 corrective 2R free-space evidence; **Sprint V3.6A**; **Sprint V3.6B**; **Sprint V3.6C**; **Sprint V4.0** kinematic geometry core; **Sprint V4.1** planar-2R intrinsic geometry atlas; **Sprint V3.6D** canonical span corpus ([`results/v3_review/v3_6d_span_corpus/`](../../results/v3_review/v3_6d_span_corpus/); [closeout](../architecture/notes/V3_6D_SPAN_CORPUS_CLOSEOUT.md); [review](../architecture/notes/V3_6D_SPAN_CORPUS_REVIEW.md)); **Sprint V3.6E** gravity-free static wrench core ([`results/v3_review/v3_6e_static_wrench_core/`](../../results/v3_review/v3_6e_static_wrench_core/); [closeout](../architecture/notes/V3_6E_STATIC_WRENCH_CORE_CLOSEOUT.md)); **Sprint V3.6F** static wrench atlas ([`results/v3_review/v3_6f_static_wrench_atlas/`](../../results/v3_review/v3_6f_static_wrench_atlas/); [closeout](../architecture/notes/V3_6F_STATIC_WRENCH_ATLAS_CLOSEOUT.md)). **Provisional** Sprint V3.7 remains non-final.

**Frozen evidence:** [V2 evidence freeze](../experiments/reports/V2_EVIDENCE_FREEZE.md). V3.5–V3.7 review packages under [`results/v3_review/`](../../results/v3_review/). V3.6D–F packages under [`results/v3_review/`](../../results/v3_review/). V4.0 smoke: [`results/v4_review/v4_0_kinematic_geometry_core/`](../../results/v4_review/v4_0_kinematic_geometry_core/). V4.1 atlas: [`results/v4_review/v4_1_planar2r_geometry_atlas/`](../../results/v4_review/v4_1_planar2r_geometry_atlas/). Do not overwrite or regenerate these packages.

**Roadmap:** V3.6D–F (completed) → next choice is Sprint V4.2 (not yet drafted / blocked) versus residual V3.7 (drafted / blocked). V4.3, if later drafted, should consume the V3.6E wrench API. The local post-V4.0 span/wrench planning bundle is [superseded](../architecture/notes/V4_POST_V4_0_SPAN_STATIC_WRENCH_BUNDLE_SUPERSEDED.md) by closed V4.1 plus V3.6D–F; do not apply it. See [ADR-027](../architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md) and [ADR-028](../architecture/adr/ADR-028-gravity-free-static-wrench.md).

**Held:** Version 2 Cartesian production inference, obstacles, MoveIt, 6R, Sprint V3.7 residual, Sprint V3.8+, Sprint V4.2+, V4.3, V4.0A kernel rewrites, production V4-006, gravity-aware wrench, force-aware planning, and deferred items (`V3-DEFER-001`, `V3-DEFER-002`).
