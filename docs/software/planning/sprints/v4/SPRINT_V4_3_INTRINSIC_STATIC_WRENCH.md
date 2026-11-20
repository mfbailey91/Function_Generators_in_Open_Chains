# Sprint V4.3 — Intrinsic Gravity-Free Static-Wrench Capability and Atlas

- **Status:** completed historical implementation; subsequent review found defects addressed by active V4.3A
- **Activated:** 2026-11-15 by the project owner's request to activate V4.3 and begin its sprint plan
- **Activation baseline:** `main` at `027d5af34e72ac33767a9538b17fb96588a2bc60`
- **Work packages closed:** V4-300–V4-309
- **Depends on:** closed V4.2B and its frozen corrected mounted-coordinate snapshots; accepted V3.6E API; completed V4.2C/V4.2D predecessor state
- **Execution state:** V4-300–V4-309 completed; implementation revision `d275b4f2`; evidence revision `f4807260`
- **Artifact target:** `results/v4_review/v4_3_intrinsic_static_wrench/`
- **Closeout:** [V4_3_INTRINSIC_STATIC_WRENCH_CLOSEOUT.md](../../../architecture/notes/V4_3_INTRINSIC_STATIC_WRENCH_CLOSEOUT.md)
- **Historical inputs not consumed:** V4.2/V4.2A and V3.6F remain retained historical evidence, not the V4.3 snapshot source
- **Next columns held:** V4.4 velocity / differential IK and V4.5 continuous flow remain separately held
- **Execution guide:** [V4_3_CURSOR_IMPLEMENTATION_ROADMAP.md](V4_3_CURSOR_IMPLEMENTATION_ROADMAP.md)
- **Authority:** accepted ADRs and method contracts, this sprint, then the current bounded Cursor implementation plan; only [ACTIVE_SPRINT.md](../../ACTIVE_SPRINT.md) grants repository authorization

**Review disposition, 2026-11-18:** preserve the original evidence and generation identities. The owner authorized [V4.3A corrective work](SPRINT_V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE.md), V4-310–V4-319, to address evidence protection, verification, record retention, diagnostics, plots, cell inspection, and final-state tests. The historical execution instructions below do not authorize regeneration of the occupied original root.

## 1. Purpose and scientific question

Evaluate the existing ideal static-wrench model over the same corrected physical configurations retained by V4.2B. V4.3 adds a provenance-checked consumer, paired capability fields, and an inspectable atlas. The accepted V3.6E API continues to own force-set mathematics.

> How does the span family redistribute a common normalized actuator torque box into planar endpoint force capacity at the same mounted-Q configurations?

The result should show where capacity increases or decreases, which force directions change, and whether a high value coincides with poor differential motion authority. It does not establish a generally superior mechanism or an application load rating.

Gravity, payload, dynamics, friction, compliance, structural limits, contact, force-aware planning, obstacles, MoveIt, 3R/6R, and new biological models remain outside this sprint. No planner campaign is reopened.

## 2. Mathematical and comparison contract

For the stored maps, use the accepted virtual-work relation:

\[
J_{xu}=J_fJ_g,\qquad A=J_{xu}^{\mathsf T},\qquad
\tau_u=AF,\qquad
\mathcal F(q)=\{F:-\bar\tau_u\le AF\le\bar\tau_u\},
\qquad \bar\tau_u=(1,1).
\]

For a unit direction \(d\), `directional_capacity` means the largest force **along that ray**, not the support function of the force polygon:

\[
\rho(d)=\max\{\alpha\ge0:\alpha d\in\mathcal F\}
=\min_{i:|a_i^{\mathsf T}d|>\epsilon}\frac{\bar\tau_i}{|a_i^{\mathsf T}d|},
\qquad
\rho_{\mathrm{iso}}=\min_{i:\|a_i\|>\epsilon}\frac{\bar\tau_i}{\|a_i\|}.
\]

The existing API owns numerical zero conventions. All-zero constraints in a direction yield an unbounded ideal direction. A zero or undefined task direction is a separate condition. An invertible but ill-conditioned matrix remains bounded; its large finite values must not be changed into infinities.

Required comparison invariants:

1. Pair `fourbar`, `span_matched_gearbox`, and `identity_on_shared_q` by the same case and stored `q_sample_id`; verify equal mounted Q and endpoint X within the inherited comparison tolerance.
2. Preserve each arm's stored U, signed Jacobians, geometry, and rank reports. Different actuator coordinates at the same physical pose are expected.
3. Keep the frozen affine gearbox span matching and the common actuator torque box. Do not retune either control to match a desired force result.
4. Make four-bar versus span-matched gearbox the primary comparison; identify identity-on-shared-Q as a separate reference.
5. Use common colour limits within each paired case/metric. Show cross-case colour policies explicitly; separately autoscaled panels must not imply a common scale.
6. Primary heatmaps use per-case mounted Q, or explicitly labelled normalized eta coordinates. Any X projection retains `q_sample_id` and branch identity; never average or maximize configurations reaching the same X into an unlabeled workspace-capacity field.
7. Summaries are descriptive over the retained uniform-Q grid, with per-case sampling measure stated. They are not uniform-workspace, application-frequency, or statistical population estimates.
8. Force values use normalized torque-per-length units. Label them in newtons only if a future explicit physical torque and length calibration supports that conversion.

The method references are [ADR-028](../../../architecture/adr/ADR-028-gravity-free-static-wrench.md), [ADR-029](../../../architecture/adr/ADR-029-mounted-output-coordinate.md), and [STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md](../../../architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md). The biological pointer is [BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md](../../../../research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md); no new biological constants or claims are authorized.

## 3. Frozen source lock and coverage

Canonical root: `results/v4_review/v4_2b_span_controlled_corrective_closeout/`.
Read case metadata from its `cases.json` and retained rows from `geometry_atlas/cases/<case_id>/geometry_samples.jsonl.gz`.

| Source property | Required value |
| --- | --- |
| Source implementation revision | `6680d648a0dc93d33f1cf34bb81cea69d6a44e80` |
| `files_digest` | `ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a` |
| `config_digest` | `ca632445469aa024c171fbc9d266ae58aeedf659e3ca3cbca5f16d70db1b6a9d` |
| `v3_6d_registry_digest` | `456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0` |
| Unique ordered cases | 17 |
| Grid per case | 33 × 33 stored Q samples |
| Arms per Q sample | `fourbar`, `span_matched_gearbox`, `identity_on_shared_q` |
| Rows per arm across cases | 18,513 |
| Total expected source rows | 55,539 = 17 × 33 × 33 × 3 |
| Canonical source typed failures / silent drops | 0 / 0 |

The core display uses `{95,145,175}²`; the biological-range display uses `{135,145,150}²`. Their shared `(145,145)` case is evaluated once and referenced twice: 17 unique cases and 18 display cells. Preserve the source classification of 175-degree cases as boundary-stress-only. Exclude those cases from any primary-certified-family aggregate and report their counts separately.

Use `verify_v4_2b_artifact` and `parse_retained_atlas_row` from the existing code. Restore the real `AtlasRow` and `KinematicGeometrySnapshot`; pass the restored snapshot to `static_wrench_from_snapshot`. The API's existing `composite_jacobian` consistency check is permitted. Re-evaluating robot geometry, resynthesizing branches, regridding Q, or choosing new rank thresholds is not.

Identify every consumed record by source case, `q_sample_id`, `mechanism_id`, and source file/digest. Preserve `mechanism_pair_id`, `grid_index`, source row schema, source revision, configuration digest, and typed source failure information. Do not invent a shipped `snapshot_id` field where the retained envelope uses this composite identity.

## 4. Execution sequence

| Phase | Work packages | Deliverable | Technical exit |
| --- | --- | --- | --- |
| A | V4-300–301 | Guard, strict schemas, source lock, retained-row consumer | Source verification, exact row accounting, adversarial guard and no-recomputation checks pass |
| B | V4-302–305 | Polygons, scalar/directional fields, statuses | Independent fixtures and focused integration tests pass |
| C | V4-306–307 | Atlas and methods | Same-bank smoke selection renders correctly and all displayed values trace to records |
| D | V4-308–309 | Canonical evidence, independent verification, closeout | Clean tested source commit, full coverage, predecessor integrity, reviewed report, authorization reset |

Tests accompany each package. V4-308 gathers final acceptance and retained evidence; it is not the first testing step. The user has authorized this sprint. Advance through these technical dependencies without inventing another permission gate.

## V4-300 — Artifact guard and schema

**State:** ready. **Depends on:** activation and the closed predecessor state.

1. Read the source-lock table and current artifact-guard patterns before introducing a writer.
2. Add a V4.3-specific write guard accepting only the canonical V4.3 root and descendants. Tests may use a monkeypatched repository root under `tmp_path`.
3. Reject traversal, escaping symlinks, sibling-prefix lookalikes, absolute paths outside the allowed root, and every frozen V3/V4 predecessor destination, including V4.2C-R and V4.2D.
4. Define strict configuration, source-lock, row, field-status, case-summary, and manifest contracts. Choose/document new V4.3 schema identifiers here; names in this plan are proposed surfaces, not shipped APIs.
5. Reject unsupported physics and unknown configuration keys at all nesting levels. Serialize torque limits and units explicitly.
6. Define the strict-JSON adapter: finite numbers remain unchanged; nonfinite/unavailable entries use `null` plus explicit unbounded, undefined, or invalid labels. Preserve the accepted API's overall status and rank information.

**Outputs:** source/config schemas, guarded output boundary, schema documentation, tests for path escapes, unsupported keys, nonfinite encoding, and overwrite refusal.

**Accept when:** adversarial paths fail before any file is created; legitimate descendant paths pass; strict JSON serializes with `allow_nan=False`; no older schema or frozen package is modified.

## V4-301 — Consume V4.2B snapshots and V3.6E

**State:** queued. **Depends on:** V4-300.

1. Verify the canonical predecessor with the existing verifier; compare all pinned source-lock values, manifest inventory, and case metadata before evaluating rows.
2. Stream the 17 compressed banks through `parse_retained_atlas_row`. Preserve source order/identity and fail on duplicate identities, missing arms, mismatched Q/X, wrong mounted provenance, or unknown cases.
3. Carry typed source failures into corresponding output failure records. Do not skip failures or substitute a freshly evaluated state.
4. Call `static_wrench_from_snapshot` for valid restored snapshots. Preserve stored rank reports and allow only the API's existing composite-map consistency check.
5. Add sentinels that fail if this consumer invokes geometry evaluation, branch synthesis, resampling, or new rank computation. Test the real imported call sites rather than an unused mock.
6. Freeze the deterministic same-bank smoke selection below; keep analytic synthetic fixtures separate from it.

**Outputs:** verified source lock, source-identity ledger, restored-row consumer, coverage accounting, deterministic smoke selection, and focused source-contract tests.

**Accept when:** exactly 55,539 source rows are accounted for, including typed failures; each arm has 18,513 records; no silent drops occur; all three arms pair at the same physical Q; tampered digests/provenance fail closed.

## V4-302 — Exact polygons

**State:** queued. **Depends on:** V4-301.

1. Retain the API's H-representation for every valid state.
2. At full-rank states, retain the API's exact torque-box vertices and order; do not construct a second force solver.
3. Check vertex feasibility and actuator-corner saturation using the stored matrix and inherited tolerances. Retain residual diagnostics and flag failures explicitly.
4. Preserve finite near-singular polygons as diagnostics while excluding them from the regular-only primary view. Singular states have no fabricated closed vertex polygon.

**Outputs:** per-state force-set records and feasibility/residual summaries.

**Accept when:** the regular analytic fixture below is recovered; every regular retained vertex satisfies the H-representation; no pseudoinverse or clipping creates artificial finite capability.

## V4-303 — Scalar field

**State:** queued. **Depends on:** V4-302.

1. Use the API's shipped `isotropic_radius` as the primary scalar; do not substitute inverse condition number, polygon area, or an ellipsoid radius.
2. Store raw values and eligibility masks separately. The primary heatmap includes only regular finite records; retain other finite diagnostic values in details.
3. Compute paired four-bar/gearbox deltas and ratios only where both records are eligible and the denominator is positive. Label unavailable comparisons and count exclusions.
4. Derive shared paired colour limits from a declared, deterministic policy. Record limits and display-only saturation without altering source values.

**Outputs:** scalar fields, comparison fields, masks, eligible-pair counts, and colour-scale metadata.

**Accept when:** every plotted cell points to an output/source identity; regular pairs use identical scales; excluded values are never replaced with zero or an artificial ratio.

## V4-304 — Directional fields

**State:** queued. **Depends on:** V4-302; may proceed alongside V4-303.

1. Use `wrench_directions.py` for `positive_x`, `positive_y`, `radial`, and `tangential`, with the inherited origin/zero-direction policy.
2. Correct the existing `directional_capacity` docstring from “support” to capacity along a ray. Its accepted algorithm and public field names remain unchanged.
3. Retain direction vectors, capacities, and per-direction finite/unbounded/undefined classifications. At the base origin, radial/tangential are undefined while Cartesian fields remain independently meaningful.
4. Add the ray-versus-support fixture below and retain existing polygon-ray tests. Keep direction normalizations and signed Jacobians consistent.

**Outputs:** four named directional fields, paired comparison masks, direction diagnostics, and the bounded terminology correction.

**Accept when:** the ray fixture yields `positive_y = 1` rather than the support value `2`; undefined directions survive strict JSON and tooltips; no direction failure suppresses unrelated valid fields.

## V4-305 — Unbounded and rank attribution

**State:** queued. **Depends on:** V4-302–304.

1. Preserve V3.6E statuses, including `regular`, `near_singular`, `rank_deficient`, `unbounded_ideal_direction`, and invalid-state information.
2. Retain rank/singular-value information for J_g, J_f, and J_xu and the API's cause attribution. Display low-gain warnings even when a scalar capacity is high.
3. Keep whole-set status distinct from per-direction classification: an unbounded strip may have finite isotropic and directional capacities.
4. Record inherited rank/direction/near-singular tolerances in methods metadata. Do not alter them to obtain cleaner figures.
5. Verify strict JSON and browser decoding for every status class using synthetic fixtures when a class is absent from the retained corpus.

**Outputs:** status masks, rank-attribution summaries, numeric transport diagnostics, and unbounded/undefined detail views.

**Accept when:** the stretched-arm fixture retains its finite `isotropic_radius = 0.5` and unbounded x direction; finite near-singular values remain finite; no singular state is marketed as practical infinite strength.

## V4-306 — HTML atlas

**State:** queued. **Depends on:** V4-303–305.

1. Build a scalar-first index with the core and biological-range matrices. Reuse the shared `(145,145)` case page while preserving both display cells.
2. Provide paired four-bar/gearbox panels and a clearly named identity reference; keep the primary comparison visually apparent.
3. Add a directional selector, status masks, paired differences/ratios, and visible eligibility/exclusion counts. Label mounted-Q or normalized-eta axes explicitly.
4. Draw sparse shape-normalized polygon glyphs only with an explicit normalization label. Give selected configurations true-scale details using common force axes.
5. Link a selected cell to raw values, Q/U/X, signed maps, torque limits, rank warnings, and source record identity. Browser code displays stored scientific values.
6. Any X projection retains configuration/branch identity; do not silently merge distinct configurations at a common Cartesian point.
7. Label stress-only cases and normalized force units. Link V4.2B as the snapshot source; older V4.2/V4.2A/V3.6F links are historical provenance only.
8. Check same-bank smoke pages before full evidence generation. Verify navigation, legends, masks, tooltips, and offline/local asset resolution.

**Outputs:** root atlas, 17 case pages, shared local assets, figure data, and representative render checks.

**Accept when:** displayed values reproduce machine-readable records; duplicate display membership does not duplicate evaluation; shape-only glyphs cannot be mistaken for magnitude; paired scales and statuses are visible.

## V4-307 — Methods and biological pointers

**State:** queued. **Depends on:** V4-301–306.

1. Write `methods.md` covering the ideal torque box, stored-snapshot consumption, virtual work, ray capacity, isotropic radius, status policy, units, source lock, and sampling measure.
2. Write the biological reference pointer using the existing trace; distinguish range-inspired cases from biological capability claims.
3. Include interpretation/nonclaim text on the atlas and README, including stress-only classification and absent load, compliance, and structural modelling.

**Outputs:** methods, biological pointer, package README, and consistent figure captions.

**Accept when:** equations/labels agree with ADR-028 and the accepted method; links resolve; no new biology or practical force rating is inferred from normalized values.

## V4-308 — Tests and retained evidence verification

**State:** queued. **Depends on:** V4-300–307 and their focused tests.

1. Reuse `tests/v3/test_v3_6e_static_wrench_core.py`; retain existing V4.0 geometry and V4.2B artifact checks. Add V4.3 tests where the new consumer, guard, schema, rendering, or provenance creates a concrete risk.
2. Run the same-bank smoke selection, independent analytic fixtures, source/no-recomputation tests, and adversarial write/schema tests before a full generation.
3. Run the full pytest regression suite before declaring implementation complete or generating retained evidence. Require touched-file lint/type checks and no new full-tree regressions against the recorded baseline. Pre-existing debt is recorded, not silently waived or expanded.
4. Finish and commit source/config/test changes. Retained generation requires a fresh clean implementation revision with the quality gate passing; the activation commit is not an implementation result.
5. Generate the canonical package once from the verified source lock. An occupied target is not silently overwritten; implement and review a V4.3 guarded staging/finalization policy or fail with a concrete recovery report.
6. Independently verify file inventory, hashes, byte counts, decompressed row counts, schema/status encoding, 17-case/three-arm coverage, pair joins, and zero silent drops.
7. Compare frozen predecessor inventories before/after: every `results/v3_review/` package and all V4 packages through V4.2D, including V4.2C-R, remain unchanged.
8. Inspect representative regular, near-boundary, stress-only, and shared-display case pages. Synthetic singular/undefined fixtures remain identified as fixtures, not observations from the retained grid.

**Outputs:** canonical packet, validation summaries, independent verifier result, and evidence of unchanged predecessors.

**Accept when:** all 55,539 rows have traceable records; there are zero unexpected parse, evaluation, serialization, or join errors; every output file is inventoried; the independent verifier passes; claims stay within the ideal normalized model. Canonical source failures are zero. Expected rank deficiency, unbounded ideal directions, near-singular diagnostics, and undefined radial/tangential directions are legitimate typed outcomes, not implementation errors. Counting a new error does not satisfy acceptance; retain its diagnostic and fix the cause before evidence retention. Commit generated evidence separately from implementation.

## V4-309 — Closeout and authorization reset

**State:** queued. **Depends on:** successful V4-308 and substantive code/evidence review.

1. For each package, record its claim, implementing code, supporting tests, why those tests are valid, retained evidence, and remaining limits.
2. Record implementation/evidence revisions, source-lock values, output digest, coverage/status counts, quality commands, predecessor integrity, and inspected pages.
3. Update current status/index surfaces to completed only after verification. A proposed note is `docs/software/architecture/notes/V4_3_INTRINSIC_STATIC_WRENCH_CLOSEOUT.md`.
4. Return `ACTIVE_SPRINT.md` to no authorization, preserve the completed sprint record, and leave V4.4/V4.5 held for their own activation.

**Outputs:** reviewed closeout note, consistent completed status, and authorization reset.

**Accept when:** the repository tells one consistent story about what was implemented and measured; no downstream sprint starts as a side effect.

## 5. Independent acceptance fixtures

These fixed expectations supplement existing API tests. They are synthetic analytic fixtures, not replacements for retained V4.2B rows.

### Regular unit-arm fixture

For L1 = L2 = 1, q = (0, pi/2), J_g = I, and torque limits (1,1), the map is `J_xu = [[-1,-1],[1,0]]`.

| Quantity | Exact expectation |
| --- | --- |
| Polygon vertices, counterclockwise | `(-1,-2), (1,0), (1,2), (-1,0)` |
| `isotropic_radius` | `1 / sqrt(2)` |
| Positive-x ray capacity | `1` |
| Positive-y ray capacity | `1` |
| Positive-y support function, diagnostic contrast only | `2` |

### Stretched unit-arm fixture

For L1 = L2 = 1, q = (0,0), J_g = I, and torque limits (1,1), use `J_xu = [[0,0],[2,1]]`.

| Quantity | Exact expectation |
| --- | --- |
| Force set | Strip `abs(F_y) <= 0.5`; F_x unbounded |
| Closed polygon vertices | Absent |
| Positive-x ray capacity | Unbounded ideal direction |
| Positive-y ray capacity | `0.5` |
| Raw `isotropic_radius` | `0.5`, retained although primary display is masked |

Keep existing virtual-work, torque scaling, rotation, vertex feasibility, and polygon-ray tests. A signed-column flip under the symmetric torque box leaves the force set invariant but must not erase the sign in the virtual-work map.

## 6. Deterministic same-bank smoke selection

Resolve actual source case IDs from `cases.json` for span pairs `(95,145)`, `(145,145)`, `(135,150)`, and `(175,145)`. Select stored `grid_index` values `(0,0)`, `(0,16)`, `(16,16)`, `(16,32)`, and `(32,32)` for all three arms: 60 source records.

Record resolved IDs, source row identities, and the selection digest before execution. Missing expected rows are source-contract failures; do not choose replacement points. This covers core, shared-display, biological-range, and stress-only cases without regridding. It need not contain every numerical status; independent fixtures cover statuses absent from the bank.

Run development smoke through a test harness with an injected temporary repository root and the same canonical V4.3 relative subtree. This test-only dependency injection does not widen the production writer's destination allowlist or create a public arbitrary-output bypass. The real canonical target remains absent until retained generation. Carry smoke selection and validation summaries into the final packet; do not intermingle synthetic fixture rows with the 55,539 retained-corpus records.

## 7. Proposed implementation surfaces and packet contract

The following new paths and CLI names are implementation proposals to be created in the stated packages. They do not exist merely because this activation plan names them. Reuse existing code when inspection identifies an equivalent supported surface.

| Proposed path or existing extension | Owner |
| --- | --- |
| Existing `src/inequality_mechanisms/audits/v4_artifact_guard.py` V4.3 extension | V4-300 |
| `src/inequality_mechanisms/experiments/v4/intrinsic_static_wrench.py` | V4-300–305 |
| `src/inequality_mechanisms/audits/v4_3_artifact.py` | V4-300/308 |
| `src/inequality_mechanisms/visualization/v4/intrinsic_static_wrench.py` | V4-306 |
| `configs/v4/intrinsic_static_wrench_v1.json` | V4-300/301 |
| `scripts/generate_v4_3_intrinsic_static_wrench.py` | V4-306/308 |
| `scripts/verify_v4_3_artifact.py` | V4-308 |
| `tests/v4/test_v4_3_*.py` grouped by guard, source, fields, and artifact risks | Each package |

Required canonical packet inventory, established during V4-300 and implemented before retention:

```text
README.md
manifest.json
config_resolved.json
environment.json
source_lock.json
schema.json
cases.json
smoke_selection.json
validation.json
coverage.json
predecessor_integrity.json
methods.md
biological_reference_pointer.md
index.html
assets/atlas.css
assets/atlas.js
fixtures/analytic_expectations.json
fixtures/analytic_results.json
cases/<case_id>/wrench_samples.jsonl.gz
cases/<case_id>/summary.json
cases/<case_id>/index.html
```

There are exactly 17 case directories. Every non-manifest file is inventoried by path, byte count, and SHA-256; the manifest excludes itself to avoid recursive hashing. The independent verifier reads without mutating the package and reports its result for closeout.

`environment.json` records Python and dependency versions, operating system/platform, numerical-library details relevant to reproduction, and the exact generation/verification commands.

`source_lock.json` distinguishes predecessor package/revision/digests from the fresh V4.3 generation revision and dirty-state flag. It records the activation baseline, source manifest hash, pinned source properties from section 3, actual source schemas, case/grid/arm identities, torque limits/units, and inherited tolerance policy. `manifest.json` records output schema versions, generation provenance, resolved config digest, output inventory/digest, complete row/status counts, and `n_silent_drops = 0`. Field names are finalized as a documented V4-300 contract; no new name is represented as an already-shipped API.

## 8. Completion and immediate next action

Completion requires working software and a verified inspectable packet: source identity preserved, no geometry recomputation, correct force semantics, strict status transport, paired visual comparisons, complete row accounting, and unchanged predecessors. Activation alone satisfies none of those implementation claims.

Start with **V4-300–301 only** using the initial prompt in the [Cursor roadmap](V4_3_CURSOR_IMPLEMENTATION_ROADMAP.md). Return a narrow implementation review with exact changed files, tests, source verification, row accounting, and any observed contract mismatch. Continue remaining authorized packages in phase order once that technical foundation passes.
