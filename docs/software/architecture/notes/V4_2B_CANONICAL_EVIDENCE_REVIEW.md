# V4.2B canonical evidence review

**Reviewed package:** [`results/v4_review/v4_2b_span_controlled_corrective_closeout/`](../../../../results/v4_review/v4_2b_span_controlled_corrective_closeout/)
**Implementation / `source_git_revision`:** `6680d648a0dc93d33f1cf34bb81cea69d6a44e80`
**Evidence commit (package contents):** `7abdb68d167f7803b314dde99222af107973857d`
**`source_git_dirty`:** `false`
**Geometry generated (UTC):** `2026-08-20T03:28:41.942068+00:00`
**Planning generated (UTC):** `2026-08-20T05:22:03.752916+00:00`
**Verifier:** `scripts/verify_v4_2b_artifact.py` accepted the package (`n_files=23`, `n_geometry_rows=55539`, `files_digest=ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a`)
**Disposition:** accept as canonical V4.2B evidence; do not retune outcomes

This note records measurements on the retained files. It does not replace
[`V4_2B_IMPLEMENTATION_REVIEW_AND_CLOSEOUT_GATE.md`](V4_2B_IMPLEMENTATION_REVIEW_AND_CLOSEOUT_GATE.md),
which reviewed the pre-generation implementation checkpoint.

Cursor-guide §11 items below were re-read from manifests, `cases.json`, all 17
`geometry_samples.jsonl.gz` files, planning `summary.json` /
`topology.jsonl.gz`, `git ls-files`, and the frozen historical-digest tests.
They were not inferred from generator-time asserts alone.

## §11 Geometry (measured)

| Item | Result |
| --- | --- |
| 17 cases | 17 `case_ids` in the root manifest and `cases.json` |
| 55,539 geometry rows or typed failures | 55,539 JSONL rows; 0 `failure_code`; 18,513 rows each for fourbar, gearbox, and identity |
| 0 silent drops | manifest `n_silent_drops=0`; recovered rows `55539 = 17 × 33 × 33 × 3` |
| mounted Q centered at zero | all 17 `q_box.lower = -q_box.upper` (atol `1e-9`); all 55,539 `snapshot.q` inside that box |
| shared Q/X within case | 18,513 sample groups; fourbar / gearbox / identity `q` and `x` agree (atol `1e-9`); 0 mismatches |
| identity `J_g = I` | all 18,513 `identity_on_shared_q` rows have `snapshot.jacobians.j_u_to_q ≈ I` |
| 175° boundary-stress label | `j1_status`/`j2_status` is `boundary_stress_only` exactly on 175° axes; other axes `certified_primary`; planning `span_175_status=boundary_stress_only` |

## §11 Planning (measured)

| Item | Result |
| --- | --- |
| 10 common tasks | `near_0`–`near_4`, `far_0`–`far_4` |
| 170 case-task cells | 17 × 10; every cell present in `summary.json` rows |
| identical final lattice edge IDs within pair | 17 topology records, one per case; one joint `admitted_topology_digest` (`d5be21554e755e80bd6e423783e0b0a8408c6e8c4f5a3b185d392bc4d5e23320`); `admitted_edge_count=candidate_edge_count=4224`; per-arm `unavailable_local_motion` rejections 0/0 |
| 0 nonfinite-cost planner exceptions | 0 rows with `status=failed` |
| all expected rows or typed failures | 2,720 rows = 17 × 10 × 8 × 2; `n_silent_drops=0` |
| OMPL unavailability retained | 680 `ompl_prm`/`ompl_rrt_connect` rows, both arms, every cell; `status=unavailable`, `skipped=ompl_unavailable`; `ompl_available=false` |

Identity-on-shared-Q is not a planner arm (planner list has no identity entry; planning mechanisms are fourbar and gearbox only).

Additional descriptive counts, not retuned: 2,028 `success`; 12 typed lattice `invalid` on task `far_2` in `span_j1_095_j2_095`, `span_j1_095_j2_145`, and `span_j1_095_j2_175`, both arms, Dijkstra and A*.

## §11 Artifact (measured)

| Item | Result |
| --- | --- |
| strict root and submanifest verification | verifier accepted root and nested `planning_audit` |
| all files tracked | 14,098 files on disk; 14,098 `git ls-files`; 0 untracked, 0 missing |
| all hashes and sizes match | verifier `files_digest` match; per-file `sha256` and `byte_count` |
| all JSONL rows strict-parse | verifier parsed every geometry JSONL row through `parse_retained_atlas_row` |
| `source_git_dirty = false` | root and planning manifests |
| `source_git_revision` = implementation commit | `6680d648a0dc93d33f1cf34bb81cea69d6a44e80`, not evidence commit `7abdb68d` |
| historical digests unchanged | `test_v4_2b_phase0_freeze.py` and `test_historical_package_digests_unchanged` passed |

Frozen V3.6D registry digest
`456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0`. Frozen
common-physical bank digest
`1416240cdf71bcba44a1962ed7510430608b5bd8f4d9923a4dbc118a4735d487`.

## Review conclusion

Every cursor-guide §11 item holds on the retained package. No outcome-driven
retuning is authorized. V4.3 remains drafted / blocked.
