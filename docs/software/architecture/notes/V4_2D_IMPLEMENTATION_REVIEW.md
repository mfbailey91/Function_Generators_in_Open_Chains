# V4.2D implementation review

**Reviewed range:** V4-240 through V4-249
**Implementation revision used for retained evidence:** `898c56f1`
**Evidence revision:** `b05b1288`
**Package:** [`results/v4_review/v4_2d_optimality_reference_report/`](../../../../results/v4_review/v4_2d_optimality_reference_report/)
**Predecessor digests (unchanged):** V4.2B `ce7bbea0…`; V4.2C `99ec523a…`
**Later drafting:** Sprint V4.3 is not activated here

Each work package is reviewed in the Phase 9 format.

## V4-240 — Sprint contract, ADR, and artifact guard

**Claim:** V4.2D may write only `results/v4_review/v4_2d_optimality_reference_report/`. Frozen V4.0–V4.2C, V4.2C-R, every `results/v3_review/` package, and V4.3 remain denied. \(J^*_{C,m}\) is the min valid direct cost on the actual V4.2C center-IK set; \(J^*_{B,m}\) is not the V4.2C denominator.

**Code that implements it:** sprint under `docs/software/planning/sprints/v4/`; `ADR-032`; `V4_2D_ALLOWED_PACKAGE` and `assert_v4_2d_output_allowed`; `configs/v4/optimality_reference_report_v1.json`.

**Tests that support it:** `tests/v4/test_v4_2d_artifact_guard.py`.

**Why the test is valid:** Allowed and nested V4.2D paths succeed; historical V4 and V3 paths fail closed without mutating predecessor bytes.

**Known failure modes:** A writer that bypasses the guard can still touch disk. Canonical scripts go through the guard.

**Remaining nonclaims:** The guard does not prove every future script will call it.

## V4-241 — V4.2C center-goal reference builder

**Claim:** 100 primary \(J^*_{C,m}\) rows are reconstructed with `CartesianDiskGoalGenerator`, `InputLinearMotion`, and `ActuatorTravelObjective`, without importing OMPL.

**Code that implements it:** `src/inequality_mechanisms/analysis/v4/optimality_reference.py`.

**Tests that support it:** `tests/v4/test_v4_2d_reference_builder.py`.

**Why the test is valid:** The committed V4.2C Stage C metadata is the oracle for generator ID and candidate count. Repeated generation is byte-identical. Already-satisfied references are zero.

**Known failure modes:** PRM sequential-goal metadata reports one accepted state and is excluded from the count check.

## V4-242 — Historical V4.2B reference loader

**Claim:** Unique `input_linear` rows per (case, task, mechanism) supply \(J^*_{B,m}\) as a representation-sensitivity control.

**Code that implements it:** `load_v4_2b_historical_references`.

**Tests that support it:** uniqueness and no-write checks in `test_v4_2d_reference_builder.py`.

**Why the test is valid:** Duplicate keys fail closed. Frozen package digests are compared before and after the read.

## V4-243 — Stage C extraction and join

**Claim:** All 6,200 Stage C rows keep task class, generator ID, IK family, exact flags, and checkpoints, and every row joins to one \(J^*_{C,m}\).

**Code that implements it:** `src/inequality_mechanisms/analysis/v4/optimality_metrics.py`.

**Tests that support it:** frozen 6,200-row join in the reference-builder test; synthetic extract tests.

**Why the test is valid:** Orphans raise. Already-satisfied rows remain typed.

## V4-244 — Optimality metric engine

**Claim:** Absolute/relative gaps, ratios, time-to-tolerance with right-censor, and \(P_\eta\) with unsolved runs in the denominator are computed against \(J^*_C\).

**Code that implements it:** `join_stage_c_to_reference`, `within_tolerance_fraction`.

**Tests that support it:** `tests/v4/test_v4_2d_optimality_metrics.py`.

**Why the test is valid:** Gaps below \(-\tau\) fail. Zero references null relative metrics. Unsolved rows lower \(P_\eta\).

## V4-245 — Pairing and final-gap decomposition

**Claim:** Pairing is index-matched, not CRN. Final gap equals goal-selection regret plus path inefficiency.

**Code that implements it:** `src/inequality_mechanisms/analysis/v4/optimality_pairing.py`.

**Tests that support it:** `tests/v4/test_v4_2d_pairing.py` plus frozen decomposition over 6,200 rows.

**Why the test is valid:** Missing mechanism arms fail. Unknown selected keys fail. Identity is checked to \(\tau\).

## V4-246 / V4-247 — Figures and HTML

**Claim:** Twelve executive figures and a question-grouped landing page with per-case pages. Local `href`/`src` resolve. Ranking tokens appear only in allowed nonclaim phrases.

**Code that implements it:** `src/inequality_mechanisms/visualization/v4/optimality_reference_report.py`.

**Tests that support it:** `tests/v4/test_v4_2d_report.py`.

**Why the test is valid:** Synthetic HTML must contain the same-seed limitation and resolve every local link.

## V4-248 — Package and verifier

**Claim:** Manifest inventory, both source digests, 100 references, 6,200 Stage C rows, zero orphans, figure files, and decomposition identities verify.

**Code that implements it:** `src/inequality_mechanisms/audits/v4_2d_artifact.py` and the generate/package/verify scripts.

**Tests that support it:** synthetic package/verify in `test_v4_2d_report.py`; live verify of the retained package during closeout.

**Artifact evidence:** `files_digest=7a04b259aa30591d33f7a008b2ad008046afd911281090cd3b8e7a15810a20b5`, `n_files=30`.

## V4-249 — Closeout and authorization reset

**Claim:** Review and closeout notes land; `ACTIVE_SPRINT.md` returns to no authorization; V4.3 stays drafted/blocked.

**Code that implements it:** this note; `V4_2D_OPTIMALITY_REFERENCE_CLOSEOUT.md`; VERSION_MATRIX / V4 plan / sprint index updates.

**Tests that support it:** `tests/v4/test_v4_2d_closeout.py` plus restored none-authorization assertions in V4.2B/V4.2C closeout tests.
