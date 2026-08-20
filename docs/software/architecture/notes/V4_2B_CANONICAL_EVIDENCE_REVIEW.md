# V4.2B canonical evidence review

**Reviewed package:** [`results/v4_review/v4_2b_span_controlled_corrective_closeout/`](../../../../results/v4_review/v4_2b_span_controlled_corrective_closeout/)
**Implementation / `source_git_revision`:** `6680d648a0dc93d33f1cf34bb81cea69d6a44e80`
**`source_git_dirty`:** `false`
**Geometry generated (UTC):** `2026-08-20T03:28:41.942068+00:00`
**Planning generated (UTC):** `2026-08-20T05:22:03.752916+00:00`
**Verifier:** `scripts/verify_v4_2b_artifact.py` accepted the package
**Disposition:** accept as canonical V4.2B evidence; do not retune outcomes

This note records the generated package. It does not replace
[`V4_2B_IMPLEMENTATION_REVIEW_AND_CLOSEOUT_GATE.md`](V4_2B_IMPLEMENTATION_REVIEW_AND_CLOSEOUT_GATE.md),
which reviewed the pre-generation implementation checkpoint.

## Coordinate and artifact checks

- Manifest package id `v4_2b_span_controlled_corrective_closeout`.
- Frozen V3.6D registry digest
  `456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0`.
- Frozen common-physical bank digest
  `1416240cdf71bcba44a1962ed7510430608b5bd8f4d9923a4dbc118a4735d487`.
- Geometry config digest
  `ca632445469aa024c171fbc9d266ae58aeedf659e3ca3cbca5f16d70db1b6a9d`.
- Root `files_digest`
  `ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a`.
- `175°` remains `boundary_stress_only`.
- Identity-on-shared-Q is not a planner arm.
- Historical `results/v3_review/` and V4.0–V4.2A packages were not rewritten.

## Geometry

- 17 span cases.
- `n_rows = 55539` (`17 × 33 × 33 × 3`).
- `n_typed_failures = 0`.
- `n_silent_drops = 0`.

## Planning audit

- 10 frozen tasks (`near_0`–`near_4`, `far_0`–`far_4`).
- 170 case-task cells.
- 8 planners × 2 mechanisms = 2720 retained rows.
- Lattice shape `(33, 33)`.
- `n_silent_drops = 0`.
- `n_typed_failures = 692`, of which:
  - 680 `ompl_unavailable` (`ompl_available = false` in this environment;
    `ompl_prm` and `ompl_rrt_connect`, both arms, every cell);
  - 12 `invalid` lattice Dijkstra/A* rows on task `far_2` in the three
    `j1=95°` cases (`span_j1_095_j2_095`, `span_j1_095_j2_145`,
    `span_j1_095_j2_175`), both arms. These remain on the page.
- Remaining 2028 rows `success`.
- Zero `failed` planner-exception rows and zero nonfinite-cost exceptions.
- One `admitted_topology_digest` per case
  (`d5be21554e755e80bd6e423783e0b0a8408c6e8c4f5a3b185d392bc4d5e23320`).
  All 17 cases share that digest: candidate and admitted edge counts are
  `4224`/`4224` with zero `unavailable_local_motion` rejections.

## Review conclusion

The package matches the V4.2B closeout checklist: clean implementation
revision, complete geometry, typed planning failures rather than silent
drops, shared final topology, and unchanged historical digests. No
outcome-driven retuning is authorized. V4.3 remains drafted / blocked.
