# V4.2A span-controlled visual planning audit closeout

**Disposition:** generated; non-inferential retained evidence
**Implementation / generation revision:** working tree on `ce9afb8f37cf86c82931c194144a2c239e6b762e` (V4.2A source was uncommitted at generation time; package `git_revision` records that HEAD)
**Audit package:** [`results/v4_review/v4_2a_span_controlled_visual_audit/`](../../../../results/v4_review/v4_2a_span_controlled_visual_audit/)
**Config digest:** `8dc2dfe67f36031831ec581afa845d0cb72cb0a7c294ec4e92235a7c6896aaa8`
**V3.6D registry digest:** `456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0`
**Generated (UTC):** `2026-08-18T00:24:45.780678+00:00`
**Work packages closed:** V4-210 through V4-219
**Contract:** 17 unique span cases × 10 frozen tasks × 8 planners = 1,360 rows; lattice \(32\times 32\) Chebyshev-1; seed 7
**Later drafting:** Sprint V4.3 does not reopen this package. No V4.2A defect review or regeneration is authorized by later sprints.

## Review conclusion

Sprint V4.2A consumes the frozen V3.6D registry by digest and runs the V3.6B visual-audit contract on the 17 unique ordered span assignments. Each case pairs:

- the V3.6D four-bar operating branch;
- its span-matched affine gearbox over the same usable \(U\) and \(Q\) intervals.

Identity-on-shared-\(Q\) is not a planner arm. Shared start \(q\) is re-resolved per case from frozen `start_u_frac` on that case’s four-bar. Cartesian disks stay the frozen V3.6 v2 X-space bank. Failures remain on the trial page. 175° remains `boundary_stress_only`. The HTML states the V3.6B no-inference statement. Frozen V3 packages and V4.0/V4.1/V4.2 were not rewritten.

This sprint described trial-scoped planning geometry. It did not rank mechanisms, compute wrench polytopes, retune `PRIMARY_CERTIFICATE`, or activate V4.3.

## Recorded outcomes (descriptive)

- 467 paired native-planner successes (both four-bar and gearbox `success`, OMPL excluded).
- 534 paired `invalid` rows: frozen Cartesian goals outside that case’s reachable \(X\).
- 340 OMPL rows `unavailable` (OMPL not installed in the generation environment).
- 19 rows with four-bar `failed` and gearbox `success`, all `lattice_dijkstra`, recorded as typed planner exceptions (non-finite lattice edge cost) rather than dropped tasks.
- Five cases have unequal lattice edge sets at 32×32 (valid-node mismatch near certified endpoints). Shared \(w_Q\)/\(w_X\) on the intersection had 0 mismatches. Notes live in each case `assets/edge_weight_note.json`.
- GIFs were skipped (`--skip-animations`). Static print panels are authoritative.

## Authorization

`ACTIVE_SPRINT.md` returns to **no code authorization**. Activating Sprint V4.3 or residual V3.7 requires a separate reviewed change. V4.2A completion does not authorize later sprints.
