# Version 4 — Kinematic Transmission Geometry

**Status:** Sprint V4.1 is **completed**. Sprints V4.2 and V4.3 are **drafted / blocked**. There is no Version 4 source-code authorization until `ACTIVE_SPRINT.md` separately activates an exact work-package range.

Version 4 keeps the planar 2R robot as a controlled exploratory system and broadens the mechanism study from graph planning into four sibling effect columns:

1. global planning and cost-to-go;
2. inverse instantaneous kinematics and velocity capability;
3. static wrench capability;
4. potential fields and continuous flow.

A Version 3 span/wrench insert ([V3.6D–F program](../../V3_POST_V3_6C_SPAN_WRENCH_PROGRAM.md)) is completed after V3.6C/V4.0/V4.1. The live Version 4 extension is the [post-V4.1 program](../../V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md): drafted V4.2 consumes the V3.6D registry; drafted V4.3 consumes the V3.6E API. Neither is authorized by this index. The local post-V4.0 span/wrench planning bundle is [superseded](../../../architecture/notes/V4_POST_V4_0_SPAN_STATIC_WRENCH_BUNDLE_SUPERSEDED.md); do not apply it.

All columns consume the same transmission geometry:

\[
\mathcal U\xrightarrow{g}\mathcal Q\xrightarrow{f}\mathcal X,
\qquad
J_{xu}=J_fJ_g.
\]

The governing architecture is [ADR-027](../../../architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md), and the program roadmap is [V4_PROJECT_PLAN.md](../../../V4_PROJECT_PLAN.md).

## Planned sequence

| Sprint | Status | Scope |
| --- | --- | --- |
| [V4.0](SPRINT_V4_0_KINEMATIC_GEOMETRY_CORE.md) | completed | Extract and verify the shared differential, metric, mobility, rank, and duality kernel. |
| [V4.1](SPRINT_V4_1_PLANAR2R_GEOMETRY_ATLAS.md) | completed | Canonical planar-2R intrinsic geometry atlas and null controls. [Cursor execution roadmap](V4_1_CURSOR_IMPLEMENTATION_ROADMAP.md). |
| [V4.2](SPRINT_V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS.md) | drafted / blocked | Span-controlled geometry-atlas extension of V4.1; consumes frozen V3.6D (V4-200–V4-208). |
| [V4.3](SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md) | drafted / blocked | Intrinsic gravity-free wrench atlas on frozen V4.2 snapshots; consumes V3.6E (V4-300–V4-309). |
| V4.4 | not yet drafted | Differential IK, actuator-rate limits, velocity sets, and tracking. |
| V4.5 | not yet drafted | Potential functions, coordinate controls, ODE integration, and flow atlases. |
| V4.6 | not yet drafted | Frozen neutral/application task banks and integrated four-column report. |
| V4.7 | not yet drafted | Paired mechanism population, calibration, pilot, production, and confirmation. |
| V4.8 | not yet drafted | Cross-column trade-space closeout and dimensional next-step decision. |

## Execution rule

Drafted sprints are implementation contracts, not automatic authorization. The current active sprint and exact allowed work packages are stated only in [`ACTIVE_SPRINT.md`](../../ACTIVE_SPRINT.md).
