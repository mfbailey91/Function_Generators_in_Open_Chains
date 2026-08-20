# Version 4 — Kinematic Transmission Geometry

**Status:** Sprint V4.1 is **completed**. Sprint V4.2 and V4.2A are **completed historical diagnostics**. Sprint V4.2B is **completed**. Sprint V4.3 remains **drafted / blocked**. Authorization is only the range named in `ACTIVE_SPRINT.md`.

Version 4 keeps the planar 2R robot as a controlled exploratory system and broadens the mechanism study from graph planning into four sibling effect columns:

1. global planning and cost-to-go;
2. inverse instantaneous kinematics and velocity capability;
3. static wrench capability;
4. potential fields and continuous flow.

A Version 3 span/wrench insert ([V3.6D–F program](../../V3_POST_V3_6C_SPAN_WRENCH_PROGRAM.md)) is completed after V3.6C/V4.0/V4.1. Sprint V4.2 consumed the V3.6D registry and is closed; Sprint V4.2A is a closed sibling visual-planning audit. Review found that their registry-consumption path retained native follower-angle offsets in the robot joint coordinate, along with bounded paired-graph, artifact, and provenance defects. The accepted [V4.2B amendment](../../V4_2B_CORRECTIVE_PROGRAM_AMENDMENT.md) inserted a fresh corrective closeout before drafted V4.3 may consume span snapshots. Canonical V4.2B evidence is retained; the [final closeout gate](V4_2B_FINAL_CLOSEOUT_GATE.md) is closed. Do not create V4.2C. The local post-V4.0 span/wrench planning bundle is [superseded](../../../architecture/notes/V4_POST_V4_0_SPAN_STATIC_WRENCH_BUNDLE_SUPERSEDED.md); do not apply it.

All columns consume the same transmission geometry:

\[
\mathcal U\xrightarrow{g}\mathcal Q\xrightarrow{f}\mathcal X,
\qquad
J_{xu}=J_fJ_g.
\]

The governing architecture is [ADR-027](../../../architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md), the mounted-coordinate correction is [ADR-029](../../../architecture/adr/ADR-029-mounted-output-coordinate.md), final paired-topology and edge-value semantics are [ADR-030](../../../architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md), and the program roadmap is [V4_PROJECT_PLAN.md](../../../V4_PROJECT_PLAN.md) as amended by V4.2B.

## Planned sequence

| Sprint | Status | Scope |
| --- | --- | --- |
| [V4.0](SPRINT_V4_0_KINEMATIC_GEOMETRY_CORE.md) | completed | Extract and verify the shared differential, metric, mobility, rank, and duality kernel. |
| [V4.1](SPRINT_V4_1_PLANAR2R_GEOMETRY_ATLAS.md) | completed | Canonical planar-2R intrinsic geometry atlas and null controls. [Cursor execution roadmap](V4_1_CURSOR_IMPLEMENTATION_ROADMAP.md). |
| [V4.2](SPRINT_V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS.md) | completed / historical | Original span-controlled geometry-atlas extension (V4-200–V4-208); retained, not overwritten. |
| [V4.2A](SPRINT_V4_2A_SPAN_CONTROLLED_VISUAL_AUDIT.md) | completed / historical | Original span-controlled visual audit (V4-210–V4-219); retained, not overwritten. |
| [V4.2B](SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md) | completed | Mounted-coordinate corrective closeout. Canonical package: `results/v4_review/v4_2b_span_controlled_corrective_closeout/`. [Closeout](../../../architecture/notes/V4_2B_SPAN_CONTROLLED_CORRECTIVE_CLOSEOUT.md). [Review](../../../architecture/notes/V4_2B_CANONICAL_EVIDENCE_REVIEW.md). |
| [V4.3](SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md) | drafted / blocked | Intrinsic gravity-free wrench atlas on frozen corrected V4.2B snapshots; unauthorized until a later activation. |
| V4.4 | not yet drafted | Differential IK, actuator-rate limits, velocity sets, and tracking. |
| V4.5 | not yet drafted | Potential functions, coordinate controls, ODE integration, and flow atlases. |
| V4.6 | not yet drafted | Frozen neutral/application task banks and integrated four-column report. |
| V4.7 | not yet drafted | Paired mechanism population, calibration, pilot, production, and confirmation. |
| V4.8 | not yet drafted | Cross-column trade-space closeout and dimensional next-step decision. |

## Execution rule

Drafted sprints are implementation contracts, not automatic authorization. The current active sprint and exact allowed work packages are stated only in [`ACTIVE_SPRINT.md`](../../ACTIVE_SPRINT.md).
