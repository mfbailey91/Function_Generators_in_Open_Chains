# V4.3A corrective patch — Cursor implementation and acceptance roadmap

Use this guide with the [authoritative corrective sprint](SPRINT_V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE.md) and current [authorization](../../ACTIVE_SPRINT.md). The patch base is `ae50709937c9b3f315e2a3a91c7a2ec974275603`, the reviewed V4.3 closeout. The patch implements the corrections; this roadmap covers applying, reviewing, validating, and retaining their results. It does not require reimplementing changes already present in the patch.

Read the [implementation validation record](../../../architecture/notes/V4_3A_IMPLEMENTATION_VALIDATION.md) for the executed gates, runtime, preview scope, and remaining acceptance limits.

## 1. Apply on an isolated branch

Inspect local changes first. Preserve unrelated work. The following assumes a clean checkout at the pinned base and a downloaded patch at a path you supply:

```bash
git status --short
git rev-parse HEAD
git switch -c sprint/v4.3a-corrective ae50709937c9b3f315e2a3a91c7a2ec974275603
git apply --check /absolute/path/V4_3A_corrective.patch
git apply /absolute/path/V4_3A_corrective.patch
git diff --check
git diff --stat
```

If the branch has advanced, inspect those commits and integrate deliberately; do not reset to the base or apply with ignored rejects. The handoff contains a patch manifest and validation note identifying the tested source state. No generated predecessor files belong in this patch.

## 2. Review the implementation by boundary

| Boundary | Files | Required review |
| --- | --- | --- |
| Production writes | `audits/v4_artifact_guard.py`, both visualization entry points | Shared preflight, exact corrective target, no deletion, original/occupied targets and symlink escapes rejected before writes |
| Scientific transport | `experiments/v4/intrinsic_static_wrench_fields.py`, config module | Full wrench fields, Hrep, task directions, source rank reports/tolerances, typed transport, v2 lineage |
| Numerical diagnostics | field builder and field tests | Absolute unit-box corner residual, valid full-rank polygon structure, corrected analytic endpoint/directions, preserved near-singular statuses |
| Independent verification | `audits/v4_3_artifact.py`, integrity tests | Actual tree enumeration, strict JSON/schema, source record joins, per-case identities/arms, derived counts, provenance, positive and adversarial v2 cases |
| Presentation | visualization module and atlas tests | Shared force coordinates, independently normalized glyphs, labeled identity scale, stored comparisons/status views, functioning offline cell inspector |
| Lifecycle | sprint/status docs, closeout tests | Original closeout historical; V4-310–319 active; corrected retention/acceptance still explicitly gated |

The public API name `torque_limits` is retained for compatibility. Read it in this intrinsic experiment as the normalized independent actuator-effort budget `(1,1)`. Do not convert this correction into a physical actuator-sizing exercise or change effort norms without a separate scientific decision.

## 3. Run the implementation gate

From the repository's supported Python environment:

```bash
python -m pip install -e '.[dev]'
python -m pytest tests/v4/test_v4_3*.py tests/v3/test_v3_6e_static_wrench_core.py -q
python scripts/check_v4_3a_quality.py
python -m pytest -q
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench
git diff --check
git diff --name-only -- results
```

The original packet's verification result is explicitly historical and pinned to its immutable v1 identity. A corrected packet must pass the strict v2 profile. Last-command result paths must be empty before corrective evidence generation; never fix a test by editing a frozen result.

Record runtime versions, actual test counts, failures/skips, and typed-check results. Compare any unrelated full-tree quality debt against the base rather than changing unrelated modules. The new scoped quality command is also a CI gate. Executed JavaScript coverage uses Node when available; record a skip if it is absent, and complete the browser acceptance check before closeout.

## 4. Inspect a temporary preview

Use the tests' isolated root injection or the generated test preview to inspect the four deterministic smoke cases. Do not expose an arbitrary production output flag or bypass source cleanliness to make a preview. Preview provenance remains test/smoke provenance.

For the atlas, inspect:

1. A regular shared sample: select grid `(32,32)` and compare both polygons on identical force axes.
2. The center row: select `(16,16)` and inspect preserved singular/near-singular statuses and unavailable fields.
3. Directional, difference, ratio, and status views: values and exclusions match the stored records.
4. Identity reference: its separate numeric scale includes its finite values and is visibly labeled.
5. Polygon glyphs: equal display size after individual normalization, with magnitude preserved in scalar/true-scale views.
6. Keyboard/local-file operation: view and grid selectors work without a server, external fetch, or scientific computation in JavaScript.

A sparse smoke preview is a UI/transport check, not coverage evidence for all 33-by-33 configurations.

## 5. Commit source, then generate fresh evidence

Complete the implementation review and commit only source/config/tests/docs. Record that implementation SHA. Require a clean working tree; the source gate must be exercised rather than monkeypatched. The configured output is a new sibling package:

```bash
git status --porcelain
git rev-parse HEAD
python scripts/generate_v4_3_intrinsic_static_wrench.py --config configs/v4/intrinsic_static_wrench_v1.json
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench_corrective
```

The original V4.3 root is permanently protected. The corrective destination must be missing or empty, and production smoke generation is also subject to the same preflight. If the corrective root is occupied, stop generation and inspect the existing attempt. The writer must never delete it. A reviewed recovery operation can move an unretained incomplete attempt aside; it cannot erase retained evidence.

The corrected packet retains 55,539 records, 17 unique cases, and three arms. It keeps the shared `(145,145)` case unique while rendering both matrix memberships, and labels all 175-degree cases as boundary stress only. The new manifest records v2 schemas and actual source/provenance/count metadata. Its predecessor record includes original V4.3.

## 6. Retention and final acceptance

Independently verify actual inventory, hashes, full scientific records, grid/arm joins, source identities, and unchanged predecessors. Inspect representative full-data pages: `(95,95)`, `(150,145)`, shared `(145,145)`, biological `(135,150)`, and stress `(175,145)`. Review the new diagnostic residual counts separately from typed source failures. Near-singular cross-platform force sensitivity stays a documented numerical limitation.

Commit evidence separately after review. Run the full regression suite again with that evidence present; the previous sprint's missing-root assumption must not recur. Record an explicit V4.3A closeout with implementation/evidence revisions, files digest, profile, gates, and limitations. Only after this final state passes should `ACTIVE_SPRINT.md` return to none. V4.4/V4.5 remain held.

## Cursor handoff prompt

> Continue the already-authorized V4.3A corrective sprint, V4-310–V4-319 only. Apply/review the supplied patch against its pinned base, preserve any later compatible work, and read the implementation validation note before rerunning gates. Preserve all frozen evidence, including original V4.3. Keep the accepted unit-box force model and frozen V4.2B ranks/maps; do not introduce motor sizing or a second kernel. Complete source validation, then generate corrected evidence from a clean committed implementation into the empty corrective root. Independently verify actual rows, identities, provenance, inventory, and all required views; rerun regression after retention. Commit evidence separately, document the review, and reset authorization only after final acceptance. Do not start V4.4/V4.5.
