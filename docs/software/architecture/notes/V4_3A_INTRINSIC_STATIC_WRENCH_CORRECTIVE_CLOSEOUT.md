# V4.3A intrinsic static-wrench corrective closeout

**Disposition:** completed after corrective source validation, clean-revision generation, independent verification, and final-state regression; V4.4/V4.5 remain held for separate activation
**Implementation revision:** `89563499`
**Evidence revision:** `c30e9a8b`
**Package:** [`results/v4_review/v4_3_intrinsic_static_wrench_corrective/`](../../../../results/v4_review/v4_3_intrinsic_static_wrench_corrective/)
**Work packages closed:** V4-310 through V4-319
**Historical predecessor:** original V4.3 package `results/v4_review/v4_3_intrinsic_static_wrench/` (`d275b4f2` / `f4807260`, digest `a7abec71…`) remains immutable
**ADR:** [`ADR-028`](../adr/ADR-028-gravity-free-static-wrench.md)
**No-inference:** corrected intrinsic gravity-free static wrench on frozen V4.2B mounted-Q snapshots; descriptive only; not an application load rating.

## What closed

Sprint V4.3A corrected the reviewed V4.3 defects in overwrite protection, verification, scientific-record retention, unit-box corner diagnostics, plot scales, interactive cell/comparison views, and final-state regression. It preserved the accepted ideal unit-effort force model and frozen V4.2B ranks/maps. Corrected evidence was generated into a sibling root; the original V4.3 package was not overwritten.

## Verified corrective package

```text
verification_profile=corrective_v2
source_git_revision=8956349952498f744e0d426d7240c900eeed1c00
source_git_dirty=false
files_digest=711608264d0fe8391f789ffcf605428cef48c262a440cd180fffa4e5fec242f4
n_files=257
n_rows=55539
n_typed_failures=0
n_silent_drops=0
status_counts: regular=53856, near_singular=561, unbounded_ideal_direction=1122
```

Reproduction / verification:

```bash
python scripts/generate_v4_3_intrinsic_static_wrench.py --config configs/v4/intrinsic_static_wrench_v1.json
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench_corrective
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench
```

Quality gates: focused V4.3 suites (136 passed, 1 skipped); `scripts/check_v4_3a_quality.py`; full pytest before evidence (1473 passed, 25 skipped); historical v1 verify unchanged; corrective v2 verify pass. Final-state regression with retained evidence present: 1474 passed, 25 skipped.

Inspected full-data pages: `(95,95)`, `(150,145)`, shared `(145,145)`, biological `(135,150)`, stress `(175,145)`.

## Known limits

Near-singular and unbounded ideal-direction outcomes remain typed API statuses, not implementation failures. Ill-conditioned radial capacities may show cross-platform numerical sensitivity; this package does not invent a new rank or clipping policy. The public field name `torque_limits` continues to mean the normalized independent actuator-effort budget `(1,1)`.

## Authorization

`ACTIVE_SPRINT.md` returns to **Code authorization: none.** Sprint V4.4 velocity / differential IK and V4.5 continuous flow remain held for their own activation.
