# V4.3B intrinsic static-wrench follow-up closeout

**Disposition:** completed after follow-up source validation, clean-revision generation, independent verification, and final-state regression; V4.4/V4.5 remain held for separate activation
**Implementation revision:** `731ae301`
**Evidence revision:** `ddfb26d5`
**Package:** [`results/v4_review/v4_3_intrinsic_static_wrench_followup/`](../../../../results/v4_review/v4_3_intrinsic_static_wrench_followup/)
**Work packages closed:** V4-320 through V4-323
**Frozen predecessors:** original V4.3 (`a7abec71…`) and V4.3A corrective (`71160826…`) remain immutable
**ADR:** [`ADR-028`](../adr/ADR-028-gravity-free-static-wrench.md)
**No-inference:** follow-up intrinsic gravity-free static wrench on frozen V4.2B mounted-Q snapshots; descriptive only; not an application load rating.

## What closed

Sprint V4.3B closed the four post-V4.3A review findings: per-direction verifier semantics (no whole-row near-singular exemption), regular-finite primary directional heatmap scales with labeled diagnostic views, vertex-diagnostic aggregates separate from typed source failures, and stale V4.3A retention wording. The accepted unit-effort force model and frozen V4.2B ranks/maps were not changed. Follow-up evidence was generated into a new sibling root; original and corrective packages were not overwritten.

## Verified follow-up package

```text
verification_profile=followup_v3
source_git_revision=731ae301962da8efbdd2d6262dc4fca0548a104a
source_git_dirty=false
files_digest=124d6c7b5701129d2f91a25dae2b6beabd546ba2498d11577b9d424a2b6cb7d6
n_files=325
n_rows=55539
n_typed_failures=0
n_silent_drops=0
status_counts: regular=53856, near_singular=561, unbounded_ideal_direction=1122
vertex_diagnostic_failures_by_status: near_singular=539 (regular=0)
```

Reproduction / verification:

```bash
python scripts/generate_v4_3_intrinsic_static_wrench.py --config configs/v4/intrinsic_static_wrench_v1.json
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench_followup
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench_corrective
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench
```

Quality gates: `scripts/check_v4_3a_quality.py`; focused V4.3 / V3.6E suites; full pytest before evidence (1481 passed, 25 skipped); historical v1 and corrective v2 verify unchanged digests; follow-up `followup_v3` verify pass. Adversarial integrity probes (collapsed near-singular polygon, well-conditioned unbounded relabel, impossible negative H-rep residual, bow-tie order) fail closed. Final-state regression with retained evidence and closeout docs present: 1483 passed, 25 skipped.

## Known limits

Near-singular and unbounded ideal-direction outcomes remain typed API statuses, not implementation failures. Ill-conditioned ray capacities may keep numerical accommodation when `|A d|` falls below the documented sensitivity floor; well-conditioned directions are verified even when whole-set status is near-singular. Real Chromium keyboard/layout E2E remains open/unclaimed; Node selection/render checks are the implemented gate. The public field name `torque_limits` continues to mean the normalized independent actuator-effort budget `(1,1)`.

## Authorization

`ACTIVE_SPRINT.md` returns to **Code authorization: none.** Sprint V4.4 velocity / differential IK and V4.5 continuous flow remain held for their own activation.
