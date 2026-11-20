# Sprint V4.3A — Intrinsic static-wrench corrective pass

- **Status:** completed; authorization reset in ACTIVE_SPRINT.md
- **Activated:** 2026-11-18 by the project owner after the V4.3 implementation review
- **Work packages closed:** V4-310–V4-319
- **Patch base:** `ae50709937c9b3f315e2a3a91c7a2ec974275603` on `v4_3-intrinsic-static-wrench`
- **Implementation revision:** `89563499`
- **Evidence revision:** `c30e9a8b`
- **Purpose:** correct the ten review findings without changing the accepted force-set model or its frozen geometry source
- **Predecessors:** [V4.3 sprint](SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md), [historical V4.3 closeout](../../../architecture/notes/V4_3_INTRINSIC_STATIC_WRENCH_CLOSEOUT.md), [ADR-028](../../../architecture/adr/ADR-028-gravity-free-static-wrench.md), [ADR-029](../../../architecture/adr/ADR-029-mounted-output-coordinate.md)
- **Closeout:** [V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE_CLOSEOUT.md](../../../architecture/notes/V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE_CLOSEOUT.md)
- **Execution guide:** [V4.3A Cursor roadmap](V4_3A_CURSOR_IMPLEMENTATION_ROADMAP.md)
- **Executed checks:** [V4.3A implementation validation](../../../architecture/notes/V4_3A_IMPLEMENTATION_VALIDATION.md)

## 1. Disposition and scope

The original V4.3 evidence remains an immutable historical package. Its regular-state values were reproduced against the accepted API, but its overwrite protections, verifier, diagnostic retention, plot scales, interactive inspection, and final-commit regression gate did not meet the sprint contract. The original closeout is not acceptance evidence for these corrections.

This sprint implements the bounded corrections, tests them, generates a fresh corrected packet from a clean implementation revision, and reviews that packet before closing. A source patch is not a newly retained evidence package. Do not label V4.3A completed merely because the patch applies or focused tests pass.

The user has authorized all ten findings. Implement in dependency order without seeking repeated permission for ordinary source, test, and documentation corrections. V4.4/V4.5 remain held. No geometry resynthesis, rank retuning, force-aware planning, 3R/6R work, hardware load model, friction, gravity, or structural-limit model belongs in this sprint.

## 2. Scientific model: normalized effort, not an actuator specification

Preserve virtual work and the signed stored composite Jacobian:

\[
\tau_u=J_{xu}^{\mathsf T}F,\qquad
\mathcal F_1(q)=\{F:\|J_{xu}^{\mathsf T}F\|_\infty\leq 1\}.
\]

The API field `torque_limits=(1,1)` means an independent **unit actuator-effort budget** for this comparison. It is a normalization of the input set, not a selected motor, thermal rating, gearbox capacity, or safe physical holding load. Fixing the input budget makes the transmission-induced force-set scale comparable at the same physical Q/X.

For a unit task direction \(d\), the ideal ray capacity is

\[
\rho(d)=\frac{1}{\|J_{xu}^{\mathsf T}d\|_\infty}
\]

when the denominator is positive. A zero denominator denotes an unbounded ideal direction in the exact formula; retained numerical classifications continue to use the accepted `direction_eps=1e-12` convention rather than introducing an exact-floating-zero test. Multiplying every effort budget by the same positive scalar \(c\) multiplies every force polygon and ray/isotropic capacity by \(c\); it leaves shapes and same-budget mechanism ratios unchanged. This is why the unit value can isolate geometry while still producing finite magnitude comparisons.

The box shape is a substantive modeling choice: it constrains each actuator independently. An aggregate Euclidean effort budget produces an ellipse at a full-rank planar state and answers a different question; its inverse image can be unbounded at a singular state. Do not silently replace the box with an ellipsoid or change actuator weights during this correction. Alternative effort norms may be discussed later as explicitly labeled sensitivity studies.

For an invertible 2-by-2 map, a force-polygon vertex is the inverse image of one of the four unit-box corners. The diagnostic called `max_corner_saturation_residual` checks that algebraic correspondence. It is not a simulation of motor saturation. Prefer **unit-box corner residual** in explanatory text while retaining established machine-readable field names.

At singular and near-singular states, retain the API's status and raw finite diagnostics. An ideal unbounded direction does not imply an infinite realizable force. Numerical corner residuals in near-singular diagnostics are counted separately from source/parse/join failures; do not alter inherited rank thresholds to improve plots or checks.

## 3. Frozen inputs and output lineage

| Item | Required value |
| --- | --- |
| Geometry source | `results/v4_review/v4_2b_span_controlled_corrective_closeout/` |
| V4.2B source revision | `6680d648a0dc93d33f1cf34bb81cea69d6a44e80` |
| V4.2B files digest | `ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a` |
| Source config digest | `ca632445469aa024c171fbc9d266ae58aeedf659e3ca3cbca5f16d70db1b6a9d` |
| Registry digest | `456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0` |
| Coverage | 17 unique ordered cases × 33 × 33 × 3 arms = 55,539 records |
| Arms | `fourbar`, `span_matched_gearbox`, `identity_on_shared_q` |
| Historical V4.3 root | `results/v4_review/v4_3_intrinsic_static_wrench/` — frozen |
| Historical V4.3 files digest | `a7abec714721afa2e4f6551990e3532e5ad9a6234f72f93b2480344fcc5d4218` |
| Corrective output root | `results/v4_review/v4_3_intrinsic_static_wrench_corrective/` |
| Corrected package/manifest/row schema | Version 2; logical package remains `v4_3_intrinsic_static_wrench` |

The original package remains readable through an explicitly historical verification profile pinned to its original complete inventory digest and implementation revision. That compatibility path must reject altered or arbitrarily downgraded packages. It does not claim the original package meets the corrected record contract.

Protect every V3 review package, all V4 packages through V4.3, and any occupied corrective target. Production entry points share one preflight and never delete-and-recreate an existing output tree. Test root injection stays internal to tests and cannot become a public arbitrary-path escape. An interrupted generation must produce a concrete recovery report; inspection or deliberately moving an unretained failed attempt is a separate, explicit operation, never an automatic writer fallback.

## 4. Work packages and acceptance

| Package | Deliverable | Depends on | Review findings |
| --- | --- | --- | --- |
| V4-310 | Corrective scope, immutable lineage, lifecycle docs | owner activation | all |
| V4-311 | Shared write preflight and containment | 310 | 1 |
| V4-312 | Complete scientific records and versioned transport | 310 | 5 |
| V4-313 | Strict independent artifact verifier | 311–312 | 4 |
| V4-314 | Correct unit-box diagnostics and analytic fixture | 312 | 6, 10 |
| V4-315 | Correct magnitude and shape displays | 312, 314 | 2, 7, 8 |
| V4-316 | Stored comparisons, status views, cell inspector | 312, 315 | 9 |
| V4-317 | Regression, lint/type, and browser gates | 311–316 | 3 and all regressions |
| V4-318 | Clean-revision corrective evidence and independent review | 317 | all |
| V4-319 | Closeout, final-state regression, authorization reset | 318 | all |

### V4-310 — Scope and lifecycle

Record this plan, current authorization, patch base, and preserved predecessor identities. Synchronize README, planning index, project/version status, ADR clarification, and historical-roadmap pointers. Preserve historical claims with a dated review qualification rather than rewriting their original generation results.

**Accept when:** there is one active authorization range, V4-310–319; no status surface represents the corrective evidence as accepted before V4-318/319; V4.4+ stays held.

### V4-311 — Evidence protection

Unify smoke and full-generation preflight. Reject canonical-root descendants as alternate package roots; protect existing trees before any write; reject symlinked roots and escaping intermediate/leaf links. Resolve paths against the intended repository anchor. Permit only the new corrective root for production generation. Remove unconditional recursive deletion from writers.

**Accept when:** root, descendant, dirty-source, nonempty target, sibling lookalike, root-symlink-to-predecessor, and child-symlink tests refuse before touching sentinels. Isolated temporary roots remain usable. Historical output fingerprints are unchanged.

### V4-312 — Scientific record retention

Retain the complete accepted wrench representation, including H-representation, torque box, signed maps, rank, vertices, task directions, capacities, classifications, and torque-amplification diagnostics. Copy all three stored source rank reports and their tolerance provenance without recomputing rank. Preserve complete source identity and distinct U coordinates for paired common Q/X.

**Accept when:** canonical v2 rows retain every required field; strict JSON round trips preserve finite, undefined, and unbounded meanings; the plotting projection cannot silently become a lossy canonical record. Use frozen-source sentinels against geometry/rank recomputation.

### V4-313 — Independent verification

Enumerate the actual tree excluding only the manifest, reject duplicate inventory paths, extra files/cases, unsafe paths/symlinks, and missing files. Parse strict JSON with duplicate-key and NaN/Infinity rejection. Validate dimensions, types, numeric/status combinations, source identities, per-case grid coverage, three-arm pairing, shared Q/X, and counts derived from records. Cross-check clean generation provenance, exact source lock, resolved-config digest, schemas, manifest inventory metadata, and predecessor integrity.

**Accept when:** each prior successful tamper probe now fails: duplicate same-arm identity with refreshed hashes; typed failure hidden by zero manifest count; missing fields with finite-labeled NaN; unlisted eighteenth case without rehashing; dirty source and malformed generation revision. Add positive v2-package coverage so an implementation that simply rejects every corrected packet cannot pass. Historical compatibility is visibly identified and cannot serve as a downgrade bypass.

### V4-314 — Diagnostics and fixture

Use absolute distance to actuator-box corners, `max(abs(abs(J_xu.T @ vertex) - torque_limits))`, separately from inequality feasibility. Reject invalid/empty/wrong-cardinality/nonfinite vertex arrays where a full-rank quadrilateral is expected. Keep near-singular failures as explicit diagnostics.

Correct the unit-link fixture endpoint to `[1,1]` at `q=(0,pi/2)`. Retain Cartesian ray capacities 1/1, isotropic radius `1/sqrt(2)`, radial `sqrt(2)`, tangential `1/sqrt(2)`, and positive-y support diagnostic 2. Preserve the stretched-strip fixture and its finite isotropic radius 0.5 with unbounded x direction.

**Accept when:** half-sized, zero, and empty fake polygons fail; regular retained vertices pass; diagnostic residuals are honest; endpoint and radial/tangential assertions detect the original fixture error. No force-kernel fork or tolerance retuning occurs.

### V4-315 — Visual scales

Use one force-coordinate domain and equal unit scale for both arms in true-scale details. Normalize each shape glyph independently before applying a common display radius. Give the identity reference an explicitly labeled full-data scale while preserving shared primary-pair limits. Store limits and any display saturation policy in metadata. Raw data are never clipped or overwritten.

**Accept when:** a 10× scaled polygon retains a 10× true-scale size difference but yields an identical normalized glyph; paired axes have identical limits; every finite identity cell is represented within its labeled range or explicit saturation markers. Inspect the previously failing `(150,145)` detail and `(95,95)` identity case.

### V4-316 — Comparison and cell inspection

Retain the helper's per-cell differences, ratios, eligibility, and reasons. Provide scalar, four directional, comparison, status, polygon-shape, identity-reference, and true-scale views. A grid-index selector is sufficient; it must select one stored physical sample and display all arms' Q/U/X, matrices, effort box, directions, rank reports, warnings, statuses, source identity, and comparison values. Keep source/configuration identity when drawing any X-related view.

Browser code may select and render stored scientific values; it must not reconstruct geometry, rank, or capacities. Selected-cell true-scale figures use Python-prepared common bounds and update with the selected sample. Support offline/local assets, clear masked/undefined/unbounded labels, and keyboard-operable controls.

**Accept when:** executed JavaScript tests select regular and center-row nonregular cells and compare displayed values against their stored records; changing view preserves explicit sample identity; unavailable ratios remain null with a reason. Inspect both core and biological cases, the shared `(145,145)` page, and a 175° stress-only page.

### V4-317 — Implementation gate

Replace tests that require canonical evidence to be absent with unchanged-before/after invariants or isolated paths. Fix new Literal type-default errors. Run all focused V4.3 tests, accepted V3.6E kernel tests, touched-file Ruff/format/mypy, and full pytest. Resolve new failures; record unrelated existing quality debt without widening it. Test the final populated-artifact state, not only the pre-generation checkout.

**Accept when:** all mandatory implementation gates pass, current-source limitations are documented, and the patch applies cleanly to its pinned base. Preserve exact commands, runtime versions, and results in the implementation validation note.

### V4-318 — Fresh evidence

Commit completed source/config/tests/docs before production generation. From that clean revision, generate the full packet exactly once into the empty corrective root using the existing CLI and updated configuration. Independently verify it, compare all frozen predecessor fingerprints including original V4.3, and review representative renders/cell interactions. Keep evidence separate from source changes in Git.

**Accept when:** 55,539 rows, 17 cases, three arms, no unexpected source/parse/serialization/join failures, strict v2 validation, complete inventory, preserved predecessors, and inspectable corrected views are established. Count near-singular diagnostic residual failures separately. Record cross-platform sensitivity of ill-conditioned radial capacities without inventing a new rank or clipping policy.

### V4-319 — Final closeout

Record implementation and evidence revisions, full inventory digest, schema profile, gate results, known model/numerical limits, and review disposition. Run regression checks again with the retained packet and final docs present. Only then mark V4.3A completed and reset authorization to none. V4.4/V4.5 require a separate activation.

## 5. Execution order and completion evidence

Proceed in four phases: (A) protection and record contract; (B) verifier, diagnostics, and views; (C) integration and full quality gate; (D) clean-revision generation, review, and closeout. Within a phase, nonoverlapping modules may be implemented in parallel. No calendar deadline or staffing capacity is assumed.

The source patch implements the corrections and includes this plan. The accompanying validation note records exactly what was executed while preparing it. V4-318/319 remain open until a clean committed implementation produces and passes review of the full corrective packet. This separation preserves reviewability and prevents a generated local preview from being mistaken for retained scientific evidence.
