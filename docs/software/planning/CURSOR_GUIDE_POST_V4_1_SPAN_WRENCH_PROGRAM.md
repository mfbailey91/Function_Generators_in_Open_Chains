# Cursor Guide — Post-V4.1 Span Geometry and Intrinsic Wrench Program

## Read first

1. `docs/software/planning/ACTIVE_SPRINT.md` (must remain **no authorization** during this planning pass)
2. `docs/software/architecture/notes/V4_1_PLANAR2R_GEOMETRY_ATLAS_CLOSEOUT.md`
3. `docs/software/architecture/notes/V3_6D_SPAN_CORPUS_REVIEW.md`
4. `docs/software/planning/V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md`
5. `docs/software/planning/sprints/v4/SPRINT_V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS.md`
6. `docs/software/planning/sprints/v4/SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md`

Do not infer authorization from a drafted sprint. Do not `git apply` the superseded `v4_post_v4_0_span_static_wrench_bundle/` patches. Do not apply `docs/software/planning/patches/v4_2_span_atlas_activation.patch` until the planning commit is reviewed.

## Handoff

Treat these as finished infrastructure:

- V4.0 `inequality_mechanisms.transmission_geometry` (`geometry_snapshot`, rank, metric, virtual power);
- V4.1 atlas machinery (`experiments/v4/shared_q_atlas.py`, `geometry_atlas.py`, `controls.py`, `visualization/v4/geometry_atlas.py`);
- V3.6D hashed span registry and 17 generated cases;
- V3.6E `metrics/static_wrench.py` and `metrics/wrench_directions.py`.

Do not create another implementation of \(J_g\), \(J_f\), \(J_{xu}\), torque-box polygons, or span synthesis.

## Phase 0 — verify the starting tree

```bash
git status --short
git rev-parse HEAD
```

Confirm:

- V4.0 and V4.1 are closed;
- V3.6D–F packages exist and are not being rewritten;
- `ACTIVE_SPRINT.md` has **code authorization: none**;
- this planning package has not modified source, tests, or `results/`.

## Activate V4.2 separately

Only after this planning commit is reviewed, apply (or recreate) the activation change in a new commit:

```bash
git apply --check docs/software/planning/patches/v4_2_span_atlas_activation.patch
git apply docs/software/planning/patches/v4_2_span_atlas_activation.patch
```

The activation text must preserve:

- V4-200–V4-208 only;
- no V4.3 source work;
- no residual V3.7;
- no writes to frozen V3 or V4.0/V4.1 packages;
- output only under `results/v4_review/v4_2_span_controlled_geometry_atlas/`.

## Cursor execution order (after activation)

### Gate 2A — guard and consume D

Implement V4-200–V4-201. Stop after the V3.6D registry digest is locked and 175° is typed `boundary_stress_only`. Do not resynthesize.

### Gate 2B — cases and shared grids

Implement V4-202–V4-203. Generate the 17 unique ordered assignments with gearbox and identity arms. Build per-case \(\eta\) grids from the V4.1 33×33 inset policy.

### Gate 2C — snapshots, ranks, HTML

Implement V4-204–V4-206. Every row is a V4.0 `geometry_snapshot`. Serialize typed failures. Two-matrix HTML with shared paired scales and a no-inference statement.

### Gate 2D — tests and closeout

Implement V4-207–V4-208. Digest-lock D, prove V4.1 bytes unchanged, then reset authorization. Do not auto-start V4.3.

## Hard rules

1. Do not reuse work-package IDs V4-100–V4-108.
2. Do not regenerate `results/v4_review/v4_1_planar2r_geometry_atlas/`.
3. Do not mutate `PRIMARY_CERTIFICATE` after seeing 175°.
4. Identity-on-shared-\(Q\) is a null control, not a ranked competitor.
5. No gravity, payload, dynamics, or force-aware planner fields.
6. V4.3, when later activated, calls V3.6E; it does not recompute Jacobians.

## Compact Cursor prompt — V4.2

> Implement only the activated V4.2 work packages V4-200–V4-208. Preserve closed V4.0/V4.1 and frozen V3.6D–F. Consume the V3.6D registry by digest; do not resynthesize spans. Extend V4.1 shared-Q snapshot machinery to the 17 unique ordered span assignments with span-matched gearboxes and identity-on-shared-Q. Call V4.0 `geometry_snapshot`. Write only `results/v4_review/v4_2_span_controlled_geometry_atlas/`. Do not implement V4.3, velocity, gravity, 3R, or MoveIt.

## Compact Cursor prompt — V4.3 (after V4.2 closeout and a separate activation)

> Implement only the activated V4.3 work packages V4-300–V4-309. Consume frozen V4.2 snapshot IDs and the V3.6E static-wrench API. Do not recompute \(J_g\), \(J_f\), or \(J_{xu}\). Write only `results/v4_review/v4_3_intrinsic_static_wrench/`. Do not overwrite V4.1 or V4.2.
