# V4.3A source-patch validation

Prepared 2026-11-18 for the accepted ten-finding corrective review.

## Scope and disposition

The patch is based on `ae50709937c9b3f315e2a3a91c7a2ec974275603` from `v4_3-intrinsic-static-wrench`. It implements the source, test, configuration, CI, and lifecycle corrections in [Sprint V4.3A](../../planning/sprints/v4/SPRINT_V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE.md). It does not contain a newly retained full corrective atlas or a V4.3A closeout claim.

Original V4.3 evidence remains readable through its explicitly historical, identity-pinned v1 profile. Newly generated corrective evidence must use the strict v2 contract and the distinct `results/v4_review/v4_3_intrinsic_static_wrench_corrective/` destination. V4-318 and V4-319 are closed after clean-revision generation, independent review, retention, final-state regression, and closeout. V4.4/V4.5 remain held.

## Executed validation

| Gate | Result |
| --- | --- |
| Complete regression suite, final source state | 1474 passed, 24 skipped, 6 warnings in 1218.18s (0:20:18) |
| Corrective Ruff and formatting | Passed for 19 files |
| Corrective mypy | Passed for six source modules |
| Existing V4.2B CI quality gate | Ruff/format passed for 32 files; mypy passed for 15 source files |
| Final focused integrity suite | 62 passed, one external pytest/anyio deprecation warning, 335.75 seconds |
| New visual/interaction regression tests | Eight passed, including execution of the actual atlas JavaScript in Node |
| Fresh smoke preview | Four cases, five retained grid locations per arm, 60 complete scientific records |
| Frozen-result preservation | All 36,659 tracked result files across 20 groups have identical before/after byte fingerprints; no result paths changed in Git |
| Patch applicability and reconstruction | Passed against the exact pinned base; applying the patch reconstructs all 32 changed files byte-for-byte with matching file modes |

The complete regression command was:

```bash
MPLBACKEND=Agg PYTHONPATH=src:. python -m pytest -q -n 4 --dist=loadfile
```

The four-worker schedule is a runtime optimization using `pytest-xdist`; it does not select a reduced test set. A serial `python -m pytest -q` remains the documented CI-compatible gate. An earlier exploratory serial run was interrupted and is not claimed as a completed validation result.

The six full-run warnings comprise five instances of the external anyio plugin's pytest deprecation warning and one Matplotlib layout warning from the unchanged V4.2D/OMPL plotting path. The 24 skipped tests are not counted as exercised coverage.

The corrective quality command was:

```bash
python scripts/check_v4_3a_quality.py
```

The existing V4.2B quality gate was executed independently using the paths in `tests/v4/data/v4_2b_lint_paths.txt`. These are scoped quality results; they do not claim a new repository-wide lint/type cleanup. The handoff bundle contains the final full regression log, corrective quality log, focused integrity log, and before/after result fingerprints.

## What the checks establish

### Evidence protection

The full and smoke generation entry points use the same `begin_v4_3_write` preflight. Production generation requires the exact corrective root, a clean source tree, and an empty target. The original V4.3 package, its descendants, all earlier review packages, symlink escapes, descendant destinations, sibling lookalikes, and occupied targets are rejected before writes. No production writer deletes an existing tree. Tests use explicitly isolated repository-root injection.

The before/after fingerprint check enumerates all tracked `results/` files using `git ls-files`, hashes each file's bytes, and groups entries by their first three path components. Each group digest hashes the sorted sequence `repository_relative_path + NUL + file_sha256 + newline`. This independent preservation digest includes manifests and is deliberately distinct from each package's own manifest inventory digest.

### Scientific records and verification

The full-corpus verifier fixture creates 55,539 new scientific rows across 17 cases and all three arms. The unmodified verifier accepts its valid v2 record/inventory contract with live frozen-source and predecessor checks. Its final test inventory contains 257 assets.

That positive verifier fixture copies historical PNGs and analytic JSON as **test-only assets** to isolate record, provenance, and inventory validation. It is not a newly generated corrected visual atlas. Fresh rendering and corrected analytic fixture values are validated separately by the math/atlas tests and the smoke preview.

Adversarial tests reject refreshed-hash packages with duplicate sample identities, hidden typed failures, missing scientific fields, invalid JSON numerics, extra cases, dirty or malformed revision provenance, legacy schema downgrades, missing required views, and escaping asset links. Additional scientific row tests reject altered isotropic magnitudes, incorrect named direction vectors, regular sources relabeled near-singular, and repeated polygon corners.

Complete retained rows include the H-representation, actuator-effort box, signed component/composite maps, task directions, capacities, statuses, torque-amplification diagnostics, all three source rank reports, inherited tolerances, and source identities. Verification checks stable force semantics against those maps and exact scientific source joins. The field builder does not resynthesize geometry or retune rank thresholds.

### Visual and interaction corrections

A data-to-pixel test establishes that a 10-times-larger force polygon remains 10 times larger on common true-scale axes. A separate test establishes that multiplying a polygon by ten leaves its independently normalized shape glyph unchanged. Identity-reference values use their own labeled full finite range while the primary pair retains common scalar limits.

The actual atlas JavaScript is executed in Node with a small DOM harness. Tests select stored regular and center-row nonregular records, change views, verify stored values and comparison exclusions, and check the three-arm selected-cell geometry scale. Browser code only selects retained data and maps vertices to display coordinates; it does not recompute scientific quantities.

The fresh smoke preview covers `(95,145)`, `(145,145)`, `(135,150)`, and the stress-only `(175,145)` case. All 60 serialized rows pass strict row validation. All local HTML asset links resolve. Generated true-scale, normalized-shape, and status PNGs were visually inspected. The corrected analytic fixture retains endpoint `[1,1]`, radial capacity approximately `1.414213562373095`, and tangential capacity approximately `0.7071067811865475`.

## Runtime

| Component | Version |
| --- | --- |
| Python | 3.12.14 |
| NumPy | 2.3.5 |
| SciPy | 1.17.0 |
| Pydantic | 2.13.4 |
| Matplotlib | 3.10.8 |
| pytest | 9.2.0 |
| pytest-xdist | 3.8.0 |
| Hypothesis | 6.170.15 |
| Ruff | 0.17.5 |
| mypy | 2.4.1 |
| Node | 24.22.3 |

The package was installed with `python -m pip install -e '.[dev]'`; `pytest-xdist` was installed separately for the complete regression run. Validation here covers this Python/runtime combination. CI continues to specify Python 3.11 and 3.12.

## Remaining acceptance limits

1. **Full corrected retention is pending.** The source patch and 60-row preview do not complete V4-318/319. Commit source first, generate all 55,539 records from that clean revision, independently verify the complete package, review representative full-data pages, retain evidence separately, and rerun final-state regression before closeout.
2. **Real-browser end-to-end inspection is pending.** Node execution and generated-image inspection passed. The headless Chromium installation attempt returned HTTP 403 in this environment, so no full browser rendering result is claimed. Review local-file operation, keyboard controls, selected-cell identity, scales, masking, and layout before final acceptance.
3. **Near-singular directional magnitudes remain cancellation-sensitive.** The verifier checks their retained source, statuses, transport, and diagnostic structure without imposing strict cross-platform replay on ill-conditioned ray magnitudes. This preserves the accepted kernel and inherited classification policy.
4. **The force sets express an ideal unit effort model.** The fixed `(1,1)` independent actuator-effort box is a normalization, not a physical motor, thermal, friction, or structural limit. The corrected corner residual checks the inverse image of unit-box corners. It does not establish a safe hardware holding load. The box-versus-Euclidean effort norm is a scientific modeling choice; this patch preserves the accepted box model.

See the [Cursor roadmap](../../planning/sprints/v4/V4_3A_CURSOR_IMPLEMENTATION_ROADMAP.md) for the exact remaining generation and acceptance sequence. The external `PATCH_MANIFEST.json` identifies the final patch digest and changed-file hashes without creating a self-referential hash inside the patch.


## Post-retention acceptance

| Item | Value |
| --- | --- |
| Implementation revision | `89563499` |
| Evidence revision | `c30e9a8b` |
| Corrective files_digest | `711608264d0fe8391f789ffcf605428cef48c262a440cd180fffa4e5fec242f4` |
| Verification profile | `corrective_v2` |
| Focused gate after apply | 136 passed, 1 skipped |
| Full pytest before evidence | 1473 passed, 25 skipped |
| Historical v1 verify | unchanged digest `a7abec71…` |
| Closeout | [V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE_CLOSEOUT.md](V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE_CLOSEOUT.md) |
