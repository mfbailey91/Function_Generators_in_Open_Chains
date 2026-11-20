# Sprint V4.3B — Intrinsic static-wrench post-review follow-up

- **Status:** completed
- **Activated:** after the V4.3A implementation review residual findings
- **Closeout:** [V4_3B_INTRINSIC_STATIC_WRENCH_FOLLOWUP_CLOSEOUT.md](../../../architecture/notes/V4_3B_INTRINSIC_STATIC_WRENCH_FOLLOWUP_CLOSEOUT.md)
- **Subsequent acceptance:** [V4.3B acceptance addendum](../../../architecture/notes/V4_3B_ACCEPTANCE_ADDENDUM.md), V4-324–V4-325; the frozen package and historical closeout remain unchanged
- **Code authorization:** none (V4-320–V4-323 closed)
- **Purpose:** close four residual findings without changing the accepted force-set model or frozen V4.2B geometry source
- **Predecessors:** [V4.3A sprint](SPRINT_V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE.md), [V4.3A closeout](../../../architecture/notes/V4_3A_INTRINSIC_STATIC_WRENCH_CORRECTIVE_CLOSEOUT.md), [ADR-028](../../../architecture/adr/ADR-028-gravity-free-static-wrench.md)
- **Artifact target:** `results/v4_review/v4_3_intrinsic_static_wrench_followup/`
- **Frozen provenance:** original `v4_3_intrinsic_static_wrench/` and corrective `v4_3_intrinsic_static_wrench_corrective/`
- **Execution guide:** [V4.3B Cursor roadmap](V4_3B_CURSOR_IMPLEMENTATION_ROADMAP.md)

## Findings addressed

| ID | Severity | Finding |
| --- | --- | --- |
| V4-321 | P2 | Verifier accepts impossible scientific records under an over-broad near-singular exemption |
| V4-322 | P2 | Near-singular outliers erase regular variation on directional heatmaps |
| V4-323a | P3 | Closeout/validation omit aggregate numerical diagnostic failure counts |
| V4-323b | P3 | Stale docs still claim V4-318/319 retention pending |

## Work packages

| ID | Scope |
| --- | --- |
| V4-320 | Authorization, lineage freeze, follow-up output guard |
| V4-321 | Verifier semantics and adversarial integrity tests |
| V4-322 | Directional display scales and color-scale regression |
| V4-323 | Diagnostic aggregation, doc reconciliation, follow-up retention, closeout |

## Nonclaims

Do not change the normalized unit-effort box, inherited rank thresholds, or V4.2B snapshots. Do not overwrite frozen V4.3/V4.3A packages. Do not claim Chromium E2E browser acceptance without a successful run. Do not start V4.4/V4.5.
