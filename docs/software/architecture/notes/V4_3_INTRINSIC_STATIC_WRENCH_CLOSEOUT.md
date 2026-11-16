# V4.3 intrinsic static-wrench closeout

**Disposition:** completed after implementation, retained generation, and independent verification; V4.4/V4.5 remain held for separate activation
**Implementation revision:** `d275b4f2`
**Evidence revision:** `f4807260`
**Package:** [`results/v4_review/v4_3_intrinsic_static_wrench/`](../../../../results/v4_review/v4_3_intrinsic_static_wrench/)
**Work packages closed:** V4-300 through V4-309
**ADR:** [`ADR-028`](../adr/ADR-028-gravity-free-static-wrench.md)
**No-inference:** V4.3 intrinsic gravity-free static wrench on frozen V4.2B mounted-Q snapshots; descriptive only; not an application load rating.

## What closed

Sprint V4.3 evaluated the accepted ideal static-wrench model on the frozen corrected V4.2B mounted-coordinate geometry corpus. It restored retained atlas rows, called `static_wrench_from_snapshot`, transported field-status labels, rendered a scalar-first offline atlas, and retained a verified package. It did not recompute Jacobians, resynthesize branches, retune rank thresholds, or overwrite V4.0–V4.2D predecessors.

## Work-package review

```text
Claim: Guarded V4.3 output root and strict schemas (V4-300).
Implementing code: audits/v4_artifact_guard.py; experiments/v4/intrinsic_static_wrench_config.py; audits/v4_3_artifact.py (transport).
Supporting tests: tests/v4/test_v4_3_artifact_guard.py, test_v4_3_schema.py — adversarial path/schema refusal.
Retained evidence: package schema.json / config_resolved.json under the V4.3 root.
Known failure modes: writing outside the allowlist; forbidden physics keys; unknown config keys.

Claim: Digest-locked V4.2B snapshot consumer (V4-301).
Implementing code: experiments/v4/intrinsic_static_wrench.py.
Supporting tests: tests/v4/test_v4_3_source_consumer.py — freeze lock, pairing, smoke selection.
Retained evidence: source_lock.json; 55,539 restored rows.
Known failure modes: predecessor digest drift; missing smoke grid identities.

Claim: Force polygons, isotropic/directional fields, status transport (V4-302–305).
Implementing code: experiments/v4/intrinsic_static_wrench_fields.py.
Supporting tests: tests/v4/test_v4_3_fields.py — analytic fixtures, ray-vs-support contrast, masks.
Retained evidence: per-row wrench_samples.jsonl.gz field records; fixtures/.
Known failure modes: conflating ray capacity with support; primary display of non-regular cells.

Claim: Scalar-first atlas and methods packet (V4-306–307).
Implementing code: visualization/v4/intrinsic_static_wrench.py; package methods/README/pointer.
Supporting tests: tests/v4/test_v4_3_atlas.py — smoke HTML/assets under injected root.
Retained evidence: index.html, case pages, figures, methods.md, biological pointer.
Known failure modes: browser recomputation; unlabeled stress-only 175° cases.

Claim: Full generator, independent verifier, retained evidence (V4-308).
Implementing code: generate_intrinsic_static_wrench_package; audits/v4_3_artifact.verify_v4_3_artifact; scripts/.
Supporting tests: tests/v4/test_v4_3_artifact.py; full pytest 1414 passed / 24 skipped before evidence.
Retained evidence: this package; verifier summary below.
Known failure modes: dirty-source generation; silent overwrite; counting new errors as acceptance.

Claim: Closeout and authorization reset (V4-309).
Implementing code: this note; ACTIVE_SPRINT.md reset; status-surface sync.
Supporting tests: documentation consistency with verified package identities.
Retained evidence: closeout note + evidence revision.
Known failure modes: auto-starting V4.4; claiming application force ratings.
```

## Frozen sources (unchanged)

```text
V4.2B files_digest=ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a
V4.2B source revision=6680d648a0dc93d33f1cf34bb81cea69d6a44e80
V4.2B n_geometry_rows=55539 (18513 per arm × 3; 17 cases; grid 33×33)
```

Predecessor git-tracked digests for every `results/v3_review/` package and V4.0–V4.2D (including V4.2C-R) were recorded in `predecessor_integrity.json` and rechecked by the independent verifier.

## Verified V4.3 package

```text
source_git_revision=d275b4f27245ac27326329427ccc82562f19624e
source_git_dirty=false
files_digest=a7abec714721afa2e4f6551990e3532e5ad9a6234f72f93b2480344fcc5d4218
config_digest=ab7eff490ffeac67424a8ae76f13aee447e78f458deeb3f4123fecbaf635ffae
n_files=206
n_rows=55539
n_typed_failures=0
n_silent_drops=0
status_counts: regular=53856, near_singular=561, unbounded_ideal_direction=1122
```

Reproduction / verification:

```bash
python scripts/generate_v4_3_intrinsic_static_wrench.py --config configs/v4/intrinsic_static_wrench_v1.json
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench
```

Quality gate before evidence: focused V4.3 suites; `tests/v3/test_v3_6e_static_wrench_core.py`; full pytest `1414 passed, 24 skipped`; Ruff clean on touched Slice D files.

Inspected pages: shared-display `span_j1_145_j2_145`, stress-only `span_j1_175_j2_145`, core `span_j1_095_j2_145`, biological-range `span_j1_135_j2_150`, plus package `index.html`.

## Allowed conclusion

Under the frozen V4.2B mounted-Q corpus and the ideal normalized torque box \((1,1)\), the package reports exact force-set geometry and ray capacities for the four-bar, span-matched gearbox, and identity-on-shared-Q controls at identical physical samples. Primary heatmaps show regular finite isotropic radius only; near-singular and unbounded ideal-direction outcomes remain typed records.

The package may not claim application load ratings, structural strength, biological force capability, general mechanism ranking, or gravity/payload/dynamics/friction/compliance/contact models.

## Authorization

`ACTIVE_SPRINT.md` returns to **Code authorization: none.** Sprint V4.4 velocity / differential IK and V4.5 continuous flow remain held for their own activation.
