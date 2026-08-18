# V3 Post-V3.6C Span/Wrench Planning Patch Manifest

**Patch:** `v3_post_v3_6c_span_wrench_program.patch`
**Prepared against main:** `db967ab31af8acab83d113812bab748384374234`
**Semantic apply point:** after V3-644 completes the V3.6C Gate A corrective closeout and returns the repository to no authorization
**Applied on:** `Version_4_Kinematic_Transmission_Geometry` after V4.1 closeout (V3-644 already satisfied)
**Patch type:** new planning/method/config files only
**Existing files modified at apply time:** V3 sprint index and architecture-notes index (drafted/blocked listings only; `ACTIVE_SPRINT.md` unchanged)
**Code authorization:** none

## Added repository files

```text
configs/v3/planar2r_span_wrench_program_v1.json
docs/research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md
docs/software/architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md
docs/software/planning/CURSOR_GUIDE_POST_V3_6C_SPAN_WRENCH_PROGRAM.md
docs/software/planning/V3_POST_V3_6C_SPAN_WRENCH_PATCH_MANIFEST.md
docs/software/planning/V3_POST_V3_6C_SPAN_WRENCH_PROGRAM.md
docs/software/planning/sprints/v3/SPRINT_V3_6D_CANONICAL_SPAN_CORPUS.md
docs/software/planning/sprints/v3/SPRINT_V3_6E_GRAVITY_FREE_STATIC_WRENCH_CORE.md
docs/software/planning/sprints/v3/SPRINT_V3_6F_STATIC_WRENCH_ATLAS_AND_BIOLOGICAL_DOCS.md
```

## Why no existing roadmap file is edited

The current repository still records V3.6C as active. The predecessor corrective guide is expected to update that state through V3-644. Editing `ACTIVE_SPRINT.md`, the V3 sprint index, or the backlog in this precomputed patch would either grant premature authorization or create a brittle context conflict with the corrective closeout.

After the planning package is committed and reviewed:

1. update the sprint index/backlog to list V3.6D–F as drafted;
2. activate V3.6D in a separate commit;
3. authorize only V3-650–V3-659;
4. repeat separate activation for E and F after each no-authorization gate.

## Validation performed on the distributed patch

The package generator performs:

- deterministic case-count assertion: 17 unique ordered cases;
- JSON parse validation;
- `git apply --check` in a clean synthetic repository;
- actual `git apply` in that repository;
- applied-file count verification;
- `git diff --check`;
- SHA-256 generation for patch and bundle.

## Scope decisions frozen by the package

- core spans: 95, 145, 175 degrees;
- biological refinement: 135, 145, 150 degrees;
- full ordered 3×3 for each group, 17 unique union;
- one canonical deterministic mechanism per unique span;
- matched gearbox over identical U/Q endpoints;
- old approximately 78-degree linkage is regression-only;
- gravity is outside the model and absent as an accepted option;
- primary atlas view is isotropic normalized force-capacity heatmap;
- directional maps and sparse exact polygons are secondary;
- 175 has typed primary/boundary-stress/unsupported outcomes;
- no force-aware planning objective in V3.6D–F.
