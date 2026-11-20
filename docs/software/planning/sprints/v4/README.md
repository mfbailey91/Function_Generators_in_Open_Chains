# Version 4 — Kinematic Transmission Geometry

**Status:** Sprint V4.1 is **completed**. Sprint V4.2 and V4.2A are **completed historical diagnostics**. Sprint V4.2B is **completed**. Sprint V4.2C is **completed**. Sprint V4.2D is **completed**. Original V4.3 evidence is frozen. Sprint V4.3A and Sprint V4.3B are **completed** (historical). [V4.3B acceptance completion](../../../architecture/notes/V4_3B_ACCEPTANCE_ADDENDUM.md) precedes **active Sprint V4.4**, authorized by the owner on 2026-11-20. V4.5 remains held.

Version 4 keeps the planar 2R robot as a controlled exploratory system and broadens the mechanism study from graph planning into four sibling effect columns:

1. global planning and cost-to-go;
2. inverse instantaneous kinematics and velocity capability;
3. static wrench capability;
4. potential fields and continuous flow.

A Version 3 span/wrench insert ([V3.6D–F program](../../V3_POST_V3_6C_SPAN_WRENCH_PROGRAM.md)) is completed after V3.6C/V4.0/V4.1. Sprint V4.2 consumed the V3.6D registry and is closed; Sprint V4.2A is a closed sibling visual-planning audit. Review found that their registry-consumption path retained native follower-angle offsets in the robot joint coordinate, along with bounded paired-graph, artifact, and provenance defects. The accepted [V4.2B amendment](../../V4_2B_CORRECTIVE_PROGRAM_AMENDMENT.md) inserted a fresh corrective closeout before V4.3 may consume span snapshots. Canonical V4.2B evidence is retained; the [final closeout gate](V4_2B_FINAL_CLOSEOUT_GATE.md) is closed. Sprint V4.2C is a completed sibling Column A planning diagnostic; Sprint V4.2D is a completed sibling optimality-reference report derived from frozen V4.2B/V4.2C packages; V4.3 was separately activated on 2026-11-15. The local post-V4.0 span/wrench planning bundle is [superseded](../../../architecture/notes/V4_POST_V4_0_SPAN_STATIC_WRENCH_BUNDLE_SUPERSEDED.md); do not apply it.

All columns consume the same transmission geometry:

\[
\mathcal U\xrightarrow{g}\mathcal Q\xrightarrow{f}\mathcal X,
\qquad
J_{xu}=J_fJ_g.
\]

The governing architecture is [ADR-027](../../../architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md), the mounted-coordinate correction is [ADR-029](../../../architecture/adr/ADR-029-mounted-output-coordinate.md), final paired-topology and edge-value semantics are [ADR-030](../../../architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md), the OMPL planner-geometry contract is [ADR-031](../../../architecture/adr/ADR-031-ompl-planner-geometry-contract.md), and the program roadmap is [V4_PROJECT_PLAN.md](../../../V4_PROJECT_PLAN.md) as amended by V4.2B.

## Planned sequence

| Sprint | Status | Scope |
| --- | --- | --- |
| [V4.0](SPRINT_V4_0_KINEMATIC_GEOMETRY_CORE.md) | completed | Extract and verify the shared differential, metric, mobility, rank, and duality kernel. |
| [V4.1](SPRINT_V4_1_PLANAR2R_GEOMETRY_ATLAS.md) | completed | Canonical planar-2R intrinsic geometry atlas and null controls. [Cursor execution roadmap](V4_1_CURSOR_IMPLEMENTATION_ROADMAP.md). |
| [V4.2](SPRINT_V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS.md) | completed / historical | Original span-controlled geometry-atlas extension (V4-200–V4-208); retained, not overwritten. |
| [V4.2A](SPRINT_V4_2A_SPAN_CONTROLLED_VISUAL_AUDIT.md) | completed / historical | Original span-controlled visual audit (V4-210–V4-219); retained, not overwritten. |
| [V4.2B](SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md) | completed | Mounted-coordinate corrective closeout. Canonical package: `results/v4_review/v4_2b_span_controlled_corrective_closeout/`. [Closeout](../../../architecture/notes/V4_2B_SPAN_CONTROLLED_CORRECTIVE_CLOSEOUT.md). [Review](../../../architecture/notes/V4_2B_CANONICAL_EVIDENCE_REVIEW.md). |
| [V4.2C](SPRINT_V4_2C_OMPL_PLANNER_GEOMETRY_PORTFOLIO.md) | completed | OMPL planner-geometry portfolio. Canonical package: `results/v4_review/v4_2c_ompl_planner_portfolio/`. Derived V4.2C-R presentation: `results/v4_review/v4_2c_r_frozen_data_report/`. [Closeout](../../../architecture/notes/V4_2C_OMPL_PLANNER_PORTFOLIO_CLOSEOUT.md). [Review](../../../architecture/notes/V4_2C_IMPLEMENTATION_REVIEW.md). [Plot guide](../../../architecture/notes/V4_2C_CLOSEOUT_REVIEW_AND_PLOT_GUIDE.md). V4.3 was separately activated on 2026-11-15. |
| [V4.2D](SPRINT_V4_2D_OPTIMALITY_REFERENCE_AND_GEARBOX_CONTROL_REPORT.md) | completed | Optimality-reference and gearbox-control report (V4-240–V4-249). Canonical package: `results/v4_review/v4_2d_optimality_reference_report/`. Reconstructs the exact V4.2C center-IK direct optimum \(J^*_{C,m}\); historical V4.2B \(J^*_{B,m}\) is a representation-sensitivity control only. [Closeout](../../../architecture/notes/V4_2D_OPTIMALITY_REFERENCE_CLOSEOUT.md). [Review](../../../architecture/notes/V4_2D_IMPLEMENTATION_REVIEW.md). [ADR-032](../../../architecture/adr/ADR-032-planner-optimality-represented-goal-reference.md). V4.3 was separately activated on 2026-11-15. |
| [V4.3](SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md) | completed / historical; reviewed defects | Original intrinsic wrench atlas (V4-300–V4-309), frozen under `results/v4_review/v4_3_intrinsic_static_wrench/`. [Historical closeout](../../../architecture/notes/V4_3_INTRINSIC_STATIC_WRENCH_CLOSEOUT.md). |
| [V4.3A](SPRINT_V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE.md) | completed / historical; residual findings | Evidence protection, complete scientific records, strict verifier, diagnostics, corrected scales, and interactive comparison views (V4-310–V4-319). Canonical package: `results/v4_review/v4_3_intrinsic_static_wrench_corrective/`. [Closeout](../../../architecture/notes/V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE_CLOSEOUT.md). |
| [V4.3B](SPRINT_V4_3B_INTRINSIC_STATIC_WRENCH_FOLLOWUP.md) | completed / historical | Post-review verifier, directional scales, diagnostic aggregation, and doc reconciliation (V4-320–V4-323). Canonical package: `results/v4_review/v4_3_intrinsic_static_wrench_followup/`. [Closeout](../../../architecture/notes/V4_3B_INTRINSIC_STATIC_WRENCH_FOLLOWUP_CLOSEOUT.md). [Cursor roadmap](V4_3B_CURSOR_IMPLEMENTATION_ROADMAP.md). |
| [V4.4](SPRINT_V4_4_VELOCITY_DIFFERENTIAL_IK.md) | active | Bounded velocity sets, explicit inverse policies, and normalized rate utilization; first instantaneous slice followed by full atlas and task-defined tracking. [ADR-033](../../../architecture/adr/ADR-033-normalized-velocity-and-explicit-inverse-policies.md). [Cursor roadmap](V4_4_CURSOR_IMPLEMENTATION_ROADMAP.md). |
| V4.5 | not yet drafted | Potential functions, coordinate controls, ODE integration, and flow atlases. |
| V4.6 | not yet drafted | Frozen neutral/application task banks and integrated four-column report. |
| V4.7 | not yet drafted | Paired mechanism population, calibration, pilot, production, and confirmation. |
| V4.8 | not yet drafted | Cross-column trade-space closeout and dimensional next-step decision. |

## Execution rule

Drafted sprints are implementation contracts, not automatic authorization. The current active sprint and exact allowed work packages are stated only in [`ACTIVE_SPRINT.md`](../../ACTIVE_SPRINT.md).
