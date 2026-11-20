# V4.3 Cursor Implementation Roadmap

**Historical roadmap:** the original implementation and evidence are retained. As of 2026-11-18 use the [V4.3A corrective roadmap](V4_3A_CURSOR_IMPLEMENTATION_ROADMAP.md) and current `ACTIVE_SPRINT.md`. Do not execute the original generation instructions against its occupied retained root. The activation narrative below records the original V4.3 phase.

## Purpose and current state

V4.3 is active as of 2026-11-15. Its activation baseline is `main` at `027d5af34e72ac33767a9538b17fb96588a2bc60`. This document turns the [authoritative sprint](SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md) into bounded implementation slices. V4-300 is ready; V4-301–309 are queued. No V4.3 code or evidence is claimed complete by activation.

Use Cursor Plan Mode to plan the current slice with exact files, symbols, tests, and commands beneath the committed sprint scope. Accepted ADRs/contracts remain authoritative. The owner's activation authorizes V4-300–309; later slices require their technical predecessors, not another permission request.

## Read first

1. `docs/software/planning/ACTIVE_SPRINT.md`
2. `docs/software/planning/sprints/v4/SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md`
3. `docs/software/architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md`
4. `docs/software/architecture/adr/ADR-028-gravity-free-static-wrench.md`
5. `docs/software/architecture/adr/ADR-029-mounted-output-coordinate.md`
6. `docs/software/architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md`
7. `docs/software/planning/sprints/v4/V4_2B_FINAL_CLOSEOUT_GATE.md`
8. `docs/research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md`

Inspect these existing implementation surfaces:

```text
src/inequality_mechanisms/experiments/v4/geometry_atlas.py
src/inequality_mechanisms/audits/v4_2b_artifact.py
src/inequality_mechanisms/audits/v4_artifact_guard.py
src/inequality_mechanisms/metrics/static_wrench.py
src/inequality_mechanisms/metrics/wrench_directions.py
src/inequality_mechanisms/transmission_geometry/
tests/v3/test_v3_6e_static_wrench_core.py
tests/v4/test_v4_2b_artifact_integrity.py
tests/v4/test_v4_2b_clean_source.py
```

The exact proposed new code paths, output inventory, numerical fixtures, and source-lock values are in the sprint. Treat them as planned implementation contracts, not existing commands.

## Existing preflight commands

Run from the repository root in its supported development environment. These commands already exist; they inspect the predecessor and run relevant baseline checks.

```bash
git status --short
git rev-parse HEAD
python scripts/verify_v4_2b_artifact.py results/v4_review/v4_2b_span_controlled_corrective_closeout
python -m pytest tests/v3/test_v3_6e_static_wrench_core.py tests/v4/test_v4_2b_artifact_integrity.py -q
```

Record the actual current revision, predecessor verifier result, and existing quality baseline. Do not confuse the predecessor's source revision `6680d648...` with the V4.3 activation or eventual generation revision. If the branch moved after activation, inspect that change and preserve compatible work; do not reset someone else's edits.

## Source facts to keep visible

The input is the frozen V4.2B root `results/v4_review/v4_2b_span_controlled_corrective_closeout/`, with `cases.json` and `geometry_atlas/cases/<case_id>/geometry_samples.jsonl.gz`.

- 17 unique cases × 33 × 33 grid points × three arms = **55,539 source records**.
- Each arm contributes **18,513** records: `fourbar`, `span_matched_gearbox`, `identity_on_shared_q`.
- Core and biological-range matrices have 18 display cells because `(145,145)` appears in both; evaluate it once.
- Preserve 175-degree stress-only classification and exact mounted-coordinate provenance.
- Use `parse_retained_atlas_row` → restored snapshot → `static_wrench_from_snapshot`.
- The existing composite-map consistency check is allowed; new geometry evaluation, branch synthesis, regridding, and rank thresholds are excluded.

## Commit and review sequence

| Slice | Packages | Intended result |
| --- | --- | --- |
| A | V4-300–301 | Guard, strict contracts, source lock, snapshot consumer, provenance tests |
| B | V4-302–305 | Force records, fields, status transport, focused mathematical/integration checks |
| C | V4-306–307 | Atlas, local assets, methods, same-bank smoke review |
| D1 | V4-308 | Complete tested implementation and independent verifier |
| D2 | V4-308 | Canonical evidence generated from the clean D1 revision, retained separately |
| D3 | V4-309 | Substantive closeout, current docs synchronized, authorization reset |

Keep implementation and generated evidence in separate commits. Tests belong with each implementation slice. Do not defer correctness checks until D1.

## Slice A — V4-300–301

### Implement

1. Extend the existing guard for the V4.3 root and test legitimate descendants, traversal, symlink escapes, prefix lookalikes, predecessor roots, and occupied targets.
2. Define strict V4.3 config/source/row/manifest contracts. Set schema identifiers once and document them. Reject unsupported physics and unknown nested keys.
3. Add strict numeric transport: finite values retained; unavailable/nonfinite values represented by `null` and an explicit reason/status. Do not rewrite the V3.6E schema.
4. Verify the full source package and exact pinned source revision/digest values in the sprint before parsing any evaluation row.
5. Restore real `AtlasRow` records, preserve composite identity and typed failures, pair the three arms at shared Q/X, and call the existing static-wrench API.
6. Account for all 55,539 rows without silent exclusions. Add failures for wrong source, duplicate/missing rows, missing arms, coordinate mismatch, altered mounted metadata, and digest mismatch.
7. Add sentinel tests proving no branch synthesis, geometry evaluation, or fresh rank computation occurs in the consumer.
8. Resolve/freeze the 60-row smoke selection from actual source case/grid identities. Do not resample or require singular states to occur in that subset.

### Review output

Report exact files/symbols, schema choices, verified source values, per-arm coverage, tests/commands, and observed mismatches. At the end of this initial slice, leave plotting and canonical generation for their later packages.

### Copy-pastable initial Cursor prompt

```text
Implement only V4.3 work packages V4-300–V4-301 for the first slice.
Read ACTIVE_SPRINT.md, SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md, this roadmap,
ADRs 027/028/029, the static-wrench method note, and V4.2B closeout.
V4.3 is already authorized; preserve package dependencies and frozen evidence.

Start by verifying the canonical V4.2B package and the sprint's exact source lock.
Implement the guarded V4.3 output boundary, strict config/source/row contracts,
and a consumer of retained compressed geometry rows. Use the existing
parse_retained_atlas_row and static_wrench_from_snapshot APIs. Preserve stored
mounted Q, U, X, signed Jacobians, rank reports, and composite source identities.
The existing composite consistency check is allowed; no new geometry evaluation,
branch synthesis, Q regridding, fallback historical bank, or rank thresholds.

Account for 17 cases × 33 × 33 × three arms = 55,539 rows, 18,513 per arm.
Preserve source failures and stress-only labels. Add strict JSON status transport,
adversarial guard/schema/provenance tests, missing/duplicate/pair-mismatch tests,
and sentinels proving the consumer does not recompute geometry or rank.
Resolve the sprint's deterministic 60-row smoke selection from the stored bank.

Return changed files/symbols, schema decisions, source verification, row counts,
tests and commands, and any concrete mismatch. Do not generate canonical V4.3
evidence or implement atlas UI in this first slice. Do not modify predecessors.
```

## Slice B — V4-302–305

Build force-set and field records from the existing API, retaining H-representation, vertices where present, scalar/directional capacities, ranks, and status diagnostics. Use regular-only finite masks for the primary display; raw finite singular diagnostics still belong in detailed records.

Correct the misleading `directional_capacity` docstring to say ray capacity. Its algorithm is the accepted method. Add the sprint's regular fixture distinguishing positive-y ray capacity `1` from support `2`, and its singular strip fixture with finite isotropic radius `0.5`.

Apply paired eligibility before differences/ratios and store exclusion reasons/counts. No numeric ratio is produced for an invalid, unbounded, undefined, or nonpositive denominator. Preserve independent Cartesian and radial/tangential field status.

Reuse existing V3.6E mathematics tests. Add checks for new source integration, strict transport, masks, and fixtures rather than duplicating every kernel test. Record inherited tolerances; no visual tuning of rank thresholds is allowed.

**Slice exit:** each record has traceable source identity; vertices/fields pass fixtures; all status classes survive strict JSON; full-rank near-singular values remain finite; every comparison has a common physical pose.

## Slice C — V4-306–307

Implement a scalar-first atlas with two range matrices, directional selector, paired common scales, masks, and a separate identity reference. Reuse the case page for `(145,145)` and label stress-only cases.

Primary axes are mounted Q or explicitly normalized eta. Any X projection retains configuration/branch identity; distinct configurations at one Cartesian point must not be silently merged into a workspace-capacity claim.

Separate shape-normalized glyphs from selected true-scale details. Details expose raw capacities, force units, torque box, Q/U/X, source identity, signed maps, and rank/low-gain warnings. Browser code displays recorded values; it does not become another scientific solver.

Write methods/README/biological pointer with accepted equations and source lineage. State normalized torque-per-length units and the sampling measure. Link V4.2B as input; identify old packages as historical.

Render the deterministic 60-row smoke subset from the stored bank through a test harness with an injected temporary repository root and the same canonical V4.3 relative subtree. This test-only path does not widen the production output allowlist or populate the real canonical target. Inspect core, biological-range, shared-display, and 175-degree stress pages. Check legends, masks, tooltips, local assets, navigation, and strict JSON decoding. Synthetic singular/origin cases remain labelled fixtures.

**Slice exit:** every visible value maps back to a result/source record; paired plots share scales; shape-only normalization is clear; local links/assets work; method text and numerical semantics agree.

## Slice D1 — Finish V4-308 implementation

Complete the proposed generator and independent read-only verifier. The generator enforces clean source, passing quality gate, exact source lock, allowed output root, and no silent overwrite. The verifier checks actual bytes and parsed rows rather than trusting counters copied from the manifest.

Required checks include inventory completeness, file SHA-256/size, 17 case directories, 55,539 corpus records, three-arm pairing, strict JSON, schema/status values, typed failures, zero silent drops, and unchanged frozen predecessors. The manifest excludes itself from its own file inventory.

Run focused V4.3 tests, the existing static-wrench suite, relevant geometry/source checks, the full pytest regression suite, and touched-file quality checks before declaring implementation complete or generating retained evidence. Compare full-tree quality results to the established baseline so pre-existing debt does not hide regressions. Commit the completed implementation before canonical generation.

## Slice D2 — Retained evidence

The following commands are **proposed future entry points**. They are unavailable until implementation creates these scripts/options and documents their help output. The exact validated CLI then becomes the reproduction recipe.

```bash
python scripts/generate_v4_3_intrinsic_static_wrench.py --config configs/v4/intrinsic_static_wrench_v1.json
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench
```

Do not generate retained evidence from this activation-only change or a dirty tree. Record the fresh tested implementation SHA, resolved config, source lock, predecessor checksums, and `environment.json` with Python/dependency/platform versions and reproduction commands. Verify the packet independently and review representative pages before retaining evidence in its own commit.

Unexpected parse, evaluation, serialization, join, or verifier errors stop evidence retention even when they were counted. Expected inherited rank/near-singular statuses, unbounded ideal directions, and undefined radial/tangential directions are legitimate outcomes and remain visible. Canonical source failures are zero; newly introduced errors are not an accepted completion category. Fix the concrete issue, commit a new clean source revision, and regenerate according to the guarded output policy. Do not relabel failed evidence as a completed sprint or erase it silently.

## Slice D3 — V4-309 closeout

For every work package, record:

```text
Claim:
Implementing code:
Supporting tests and why they are valid:
Retained evidence and source identities:
Known failure modes and remaining nonclaims:
```

The closeout records source/evidence revisions, package digest, coverage/status counts, exact reproduction/verification commands, quality results, unchanged predecessors, and inspected pages. Synchronize current docs, return `ACTIVE_SPRINT.md` to no authorization, and leave V4.4/V4.5 held.

## What to carry into the next implementation session

Keep this sprint, its phase/package status, exact source lock, current implementation revision, and last passing test/verifier results together. Resume the next queued package from that record. No phase may quietly change the source corpus, torque model, physical-state comparison, or accepted numerical tolerances.
