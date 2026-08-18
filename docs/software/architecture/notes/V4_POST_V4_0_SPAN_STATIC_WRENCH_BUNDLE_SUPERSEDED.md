# Post-V4.0 span/static-wrench planning bundle — superseded

**Status:** superseded — do not apply; do not treat as a live V4.1 or V4.2 contract
**Bundle reviewed:** `v4_post_v4_0_span_static_wrench_bundle/`
**Bundle baseline:** `ff8e23f` (V4.0 closed; V4.1 not yet shipped)
**Follow-up:** do not apply this bundle. The live post-V4.1 draft is [V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md](../../planning/V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md) (V4.2/V4.3; unauthorized). Closed V4.1 plus V3.6D–F remain the shipped owners of the legacy atlas and the span/wrench insert. Do not `git apply` the bundle patches, and do not regenerate any frozen package from this note.

The drop is a pre-V4.1 planning package. It would have made V4.1 a span-defined geometry atlas (`results/v4_review/v4_1_planar2r_span_geometry_atlas/`) and V4.2 a wrench atlas, with a second ADR-028 filename (`ADR-028-v4-intrinsic-static-wrench-semantics.md`). That split did not ship.

## Mapping to the shipped tree

| Bundle proposal | Shipped owner | Do not |
| --- | --- | --- |
| V4.1 span-defined atlas, five target spans, 17-case corpus | [V3.6D](V3_6D_SPAN_CORPUS_CLOSEOUT.md) (`results/v3_review/v3_6d_span_corpus/`); frozen V4.1 geometry atlas stays the legacy ~78° pair at `results/v4_review/v4_1_planar2r_geometry_atlas/` | Relabel or regenerate V4.1 as a span atlas |
| V4.2 intrinsic gravity-free wrench atlas | [V3.6E](V3_6E_STATIC_WRENCH_CORE_CLOSEOUT.md) / [V3.6F](V3_6F_STATIC_WRENCH_ATLAS_CLOSEOUT.md) | Redo wrench as a new V4.2 package |
| ADR-028 as Version 4 wrench semantics | Existing [ADR-028](../adr/ADR-028-gravity-free-static-wrench.md) (accepted for E/F; drafted V4.3 consumes that API) | Add a second ADR-028 file |
| Activation V4-100–V4-111 | Closed [V4.1](../../planning/sprints/v4/SPRINT_V4_1_PLANAR2R_GEOMETRY_ATLAS.md) already used **V4-100–V4-108** | Re-authorize those IDs for a different sprint |

This bundle is not the live V4.2 contract. Drafted V4.2 is the span-controlled geometry extension; drafted V4.3 is the Version 4 intrinsic wrench atlas. Velocity moves to V4.4.

## Do not apply

- `v4_post_v4_0_span_static_wrench_planning.patch`
- `v4_1_span_geometry_atlas_activation.patch`

Applying either patch would collide with closed V4.1 names and work packages, duplicate ADR-028, and reopen V3.6D–F under Version 4 numbering.

The local bundle directory and its patches stay untracked. They are not implementation authority.

## Non-goals

This note does not authorize V4.2, V4.3, or residual V3.7. Code authorization remains none until `ACTIVE_SPRINT.md` names an exact work-package range.
