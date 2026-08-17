# Patch Manifest — Post-V4.1 Span Geometry and Intrinsic Wrench Program

**Planning package:** this commit’s documentation and draft config only
**Prepared against:** `9b49dba` on `Version_4_Kinematic_Transmission_Geometry`
**Patch type:** planning/method/config files; no source, tests, or results
**`ACTIVE_SPRINT.md` in the planning commit:** unchanged (no code authorization)
**Activation patch:** `docs/software/planning/patches/v4_2_span_atlas_activation.patch` (written, **not applied**)

## Added repository files

```text
configs/v4/planar2r_span_controlled_atlas_v1.json
docs/software/planning/CURSOR_GUIDE_POST_V4_1_SPAN_WRENCH_PROGRAM.md
docs/software/planning/V4_POST_V4_1_SPAN_WRENCH_PATCH_MANIFEST.md
docs/software/planning/V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md
docs/software/planning/patches/v4_2_span_atlas_activation.patch
docs/software/planning/sprints/v4/SPRINT_V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS.md
docs/software/planning/sprints/v4/SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md
```

## Existing files modified by the planning pass

```text
docs/software/VERSION_MATRIX.md
docs/software/V4_PROJECT_PLAN.md
docs/software/architecture/adr/ADR-028-gravity-free-static-wrench.md
docs/software/architecture/adr/README.md
docs/software/architecture/notes/README.md
docs/software/architecture/notes/V4_1_PLANAR2R_GEOMETRY_ATLAS_CLOSEOUT.md
docs/software/architecture/notes/V4_POST_V4_0_SPAN_STATIC_WRENCH_BUNDLE_SUPERSEDED.md
docs/software/planning/README.md
docs/software/planning/sprints/v4/README.md
```

Do not modify `ACTIVE_SPRINT.md`, `src/`, `tests/`, or `results/` in the planning commit.

## Roadmap after the planning pass

```text
V4.0  accepted geometry kernel                         closed
  └── V4.1  legacy ~78° intrinsic geometry atlas       closed
        └── V4.2  span-controlled geometry extension   drafted / blocked
              └── V4.3  intrinsic static-wrench atlas  drafted / blocked
                    └── V4.4  velocity / differential IK
                          └── V4.5  potential flow
                                └── V4.6  integrated application corpus
                                      └── V4.7  mechanism population
                                            └── V4.8  cross-column closeout
```

Residual V3.7 remains a separately blocked choice.

## Apply order

1. Review and commit this planning package with `ACTIVE_SPRINT.md` still unauthorized.
2. After review, apply `v4_2_span_atlas_activation.patch` in a **separate** commit to authorize V4-200–V4-208 only.
3. Do not apply the superseded `v4_post_v4_0_span_static_wrench_bundle/` patches.
4. Do not activate V4.3 until V4.2 closeout returns the repository to no authorization.

## Scope decisions frozen by the package

- V4.1 evidence remains immutable; V4-100–V4-108 are not reused.
- V4.2 consumes the V3.6D registry by digest; it does not resynthesize 95/135/145/150/175.
- 175° stays `boundary_stress_only`; `PRIMARY_CERTIFICATE` is not retuned.
- 18 labeled cells, 17 unique ordered cases; `(145,145)` has two memberships.
- Each nonlinear module has a span-matched gearbox and identity-on-shared-\(Q\).
- V4.3 consumes V3.6E; it does not fork a wrench kernel.
- Gravity, payload, dynamics, contact, and structural models are absent.
