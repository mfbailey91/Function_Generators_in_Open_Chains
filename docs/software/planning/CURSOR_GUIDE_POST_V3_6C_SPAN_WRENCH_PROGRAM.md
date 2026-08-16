# Cursor Guide — Post-V3.6C Canonical Spans and Static Wrench Program

## Use this guide only after V3-644

Do not begin this work while the V3.6C Gate A corrective closeout is active.

Prerequisite state:

1. V3-640–V3-644 completed and reviewed;
2. the V3.6C corrective artifact committed separately from implementation;
3. frozen V3.6/V3.6B/V3.6C/provisional-V3.7 artifacts unchanged;
4. `docs/software/planning/ACTIVE_SPRINT.md` says no code authorization;
5. working tree clean and tests green.

This patch adds planning and methods documents only. It intentionally does not edit `ACTIVE_SPRINT.md` or authorize source changes.

## Apply-time amendments (this branch)

Applied on `Version_4_Kinematic_Transmission_Geometry` after V3.6C, V4.0, and V4.1 closeout. Prerequisite V3-644 is satisfied. `ACTIVE_SPRINT.md` remains unauthorized.

Amendments versus the raw patch:

1. The biological joint-range trace lives at `docs/research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md` (canonical research path), not `docs/literature/`.
2. The V3 sprint index lists V3.6D–F as drafted/blocked. That listing is not activation.
3. V4.0 `inequality_mechanisms.transmission_geometry` is the authoritative Jacobian, metric, rank, and virtual-power kernel. Later V3.6E activation must consume it rather than rederive \(J_g\), \(J_f\), \(J_{xu}\), or virtual-work identities.
4. V4.3 remains the Version 4 wrench column. This V3.6D–F program is a drafted 2R span/wrench insert, not a substitute for V4.3 and not authorization to start either.
5. Frozen evidence now also includes the retained V4.0 smoke and V4.1 atlas packages. Do not overwrite them.

## Apply the planning patch

```bash
git status --short
git apply --check v3_post_v3_6c_span_wrench_program.patch
git apply v3_post_v3_6c_span_wrench_program.patch
git diff --check
git status --short
```

Review these contracts first:

1. `docs/software/planning/V3_POST_V3_6C_SPAN_WRENCH_PROGRAM.md`
2. `docs/software/planning/sprints/v3/SPRINT_V3_6D_CANONICAL_SPAN_CORPUS.md`
3. `docs/software/planning/sprints/v3/SPRINT_V3_6E_GRAVITY_FREE_STATIC_WRENCH_CORE.md`
4. `docs/software/planning/sprints/v3/SPRINT_V3_6F_STATIC_WRENCH_ATLAS_AND_BIOLOGICAL_DOCS.md`
5. `docs/software/architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md`
6. `docs/research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md`

Commit the planning package independently from implementation.

## Activate V3.6D separately

Only after the planning commit is reviewed, edit `ACTIVE_SPRINT.md` in a new change to authorize exactly V3-650–V3-659.

The activation text must preserve these conditions:

- V3.6D only;
- no wrench implementation before V3.6D closes;
- no V3.7 reconciliation;
- no writes to frozen evidence directories;
- output only under `results/v3_review/v3_6d_span_corpus/`.

## Cursor execution order

### Gate D1 — contract and registry

Implement V3-650–V3-653:

- artifact freeze guard;
- span taxonomy and range semantics;
- deterministic synthesis interface;
- canonical registry and provenance.

Stop and inspect the five mechanism records before building any planning or wrench atlas.

### Gate D2 — matched controls and cases

Implement V3-654–V3-656:

- equivalent gearboxes;
- generated 17-case ordered union;
- characterization tables and plots.

Do not hand-author case IDs. Generate and deduplicate them from the two span sets.

### Gate D3 — tests and artifact

Implement V3-657–V3-659:

- invariants and regression tests;
- config/export schema;
- clean code commit, then clean artifact commit;
- review and return to no authorization.

### Gate E — wrench mathematics

Activate V3.6E separately and implement V3-660–V3-669. Keep the mathematics independent of HTML rendering. The solver must return typed records for nonsingular, near-singular, rank-deficient, and unbounded-ideal-direction states.

### Gate F — atlas and documentation

Activate V3.6F separately and implement V3-670–V3-679. The main index view is the scalar isotropic-capacity heatmap. Directional maps and exact polygons remain inspectable secondary views.

## Hard implementation rules

1. Search/planner state semantics remain unchanged: U is the physical mechanism state; Q and X are projections unless a shared-Q comparison is explicitly declared.
2. The target range is `Q_usable`, not the entire rocker stroke.
3. The old approximately 78-degree four-bar is regression-only.
4. Do not alter the common synthesis certificate to rescue 175 degrees after seeing results.
5. No gravity term, gravity config key, payload field, or gravity-adjusted plot is permitted in V3.6D–F.
6. The 2R “wrench” is a planar endpoint force vector `[Fx,Fy]`; do not add an end-effector moment component.
7. Exact actuator torque-box polygons are authoritative. Ellipsoids may be derived only as clearly labeled summaries.
8. Visual clipping never changes computed values. Singular or unbounded ideal cases receive masks/statuses.
9. Same case, same Q grid, same normalized actuator limits, and shared paired color scales for four-bar/gearbox plots.
10. No force-aware planner objective yet. This program characterizes the field first.

## Expected commands

Exact entry points may follow existing exporter conventions, but the final interface should be approximately:

```bash
python scripts/export_v3_6d_span_corpus.py \
  --config configs/v3/planar2r_span_wrench_program_v1.json

python scripts/export_v3_6e_static_wrench_core.py \
  --config configs/v3/planar2r_span_wrench_program_v1.json

python scripts/export_v3_6f_static_wrench_atlas.py \
  --config configs/v3/planar2r_span_wrench_program_v1.json
```

Each exporter must refuse frozen output directories and write a manifest containing code revision, config hash, registry hash, schema versions, synthesis certificate, task/case IDs, and result checksums.

## Final review questions

- Did 175 pass the same certificate, become boundary-stress-only, or fail explicitly?
- Are 135/145/150 all represented on both proximal and distal axes?
- Does the force polygon satisfy `tau_u = J_xu.T @ w` at every vertex?
- Does the scalar heatmap agree with directional ray intersections?
- Are serial-arm singularities distinguished from four-bar low-gain regions?
- Are normalized ideal capability and safe/biological force clearly separated?
- Is gravity absent from schema, code path, results, and prose?
- Are all old artifacts unchanged?
