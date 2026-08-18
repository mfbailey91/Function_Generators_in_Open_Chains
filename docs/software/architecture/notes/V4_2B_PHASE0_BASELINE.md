# V4.2B Phase 0 baseline freeze

**Disposition:** freeze snapshot before corrective implementation; not a sprint closeout
**Recorded HEAD:** `5e1fce0c3e3f7e62f33fef7b6feffd2e76d0bcf2`
**Lineage:** descendant of reviewed `db398268bf2de7efc8ca7ab33e49d787c8b4cef4` via planning `2f098afa` and activation `5e1fce0c`
**Authorization:** V4-220–V4-229 only
**Captured (UTC):** 2026-08-18 during Phase 0 on `Version_4_Kinematic_Transmission_Geometry`

This note records the historical packages V4.2B must not mutate. V4.2 and V4.2A remain immutable historical evidence. Phase 0 does not implement mounted coordinates, paired-topology repair, generators, or a V4.2B writer root.

## Commands

```bash
git status --short
git rev-parse HEAD
PYTHONPATH=src .venv/bin/python -m pytest tests/v4 -q
```

Tracked working tree: clean (no modified tracked files). Untracked leftovers: 309 paths, including Finder ` 2` duplicates, leftover `.patch` files, and superseded planning bundles. None of those leftovers were staged or regenerated.

## Frozen V3.6D registry

- path: `results/v3_review/v3_6d_span_corpus/registry.json`
- digest: `456efd9f9472f8cee6271347e4e13bc750473bc186f752a254c526cc853296f0`

Matches `FROZEN_V3_6D_DIGEST`. Synthesis was not called. The registry was not rewritten.

## Git-tracked package digests

| Package | `n_files` | SHA-256 |
| --- | ---: | --- |
| V4.0 `v4_0_kinematic_geometry_core` | 12 | `963a52e1908c0a2997fb94c25224ca268653a30b3a65a6e26126af27d8d88b1d` |
| V4.1 `v4_1_planar2r_geometry_atlas` | 26 | `6a3f1d7456228ed9126a72bcf22d87e10360a852f5218a7c8ed73e5986330c87` |
| V4.2 `v4_2_span_controlled_geometry_atlas` | 380 | `2517ac24d2cce4fd54fd8df1ab569a079fb00c5ceca94e70142f6d5369ec015e` |
| V4.2A `v4_2a_span_controlled_visual_audit` | 12535 | `ccfd012b228fe18c70ac3ff7776aa4225aaec8eb8bd6fde93545d53675818763` |

V4.0 and V4.1 match the existing lock files. V4.2 and V4.2A locks are new Phase 0 files under `tests/v4/data/`. The V4.2 git-tracked digest excludes gitignored `geometry_samples.jsonl`. `v4_2_atlas_package_digest()` remains the on-disk tree hash used by V4.2A generation equality tests.

V3 retained-package digests remain those locked by `tests/v4/data/frozen_v3_review_digests.json`.

## `tests/v4` baseline

- 116 passed
- 1 failed: `tests/v4/test_v4_009_closeout.py::test_v4_0_closeout_did_not_auto_authorize_later_columns`
- duration: 99.31 s

The failure asserts `**Code authorization:** none` in `ACTIVE_SPRINT.md`. That string is absent because Sprint V4.2B is authorized. It is not a retained-package mutation. Phase 0 does not reset authorization.

## OMPL provenance

OMPL Python bindings are unavailable in this capture environment (`is_ompl_available() is False`; version `None`). Unavailability is environment provenance only and does not block Phase 0 or later V4.2B closeout.

## What Phase 0 did not do

- no mounted-coordinate adapter
- no V4.2B allowed-writer root
- no atlas or audit regeneration
- no `results/v4_review/v4_2b_span_controlled_corrective_closeout/`
- no `VERSION_MATRIX.md` edit
