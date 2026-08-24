# V4.2C implementation review

**Reviewed range:** V4-230 through V4-239
**Implementation revision used for retained evidence:** `5320d6f336ef82615a51f7826d0febd39c18f9db`
**Package:** [`results/v4_review/v4_2c_ompl_planner_portfolio/`](../../../../results/v4_review/v4_2c_ompl_planner_portfolio/)
**Predecessor V4.2B digest (unchanged):** `ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a`
**OMPL used for generation:** Python 3.13.15 and pip wheel `ompl==2.0.1` (project `.venv` is CPython 3.14 and has no matching wheel)
**Later drafting:** Sprint V4.3 is not activated here

Each work package is reviewed in the Phase 9 format.

## V4-230 — Contract landing, ADR, and artifact guard

**Claim:** V4.2C may write only `results/v4_review/v4_2c_ompl_planner_portfolio/`. Frozen V4.0–V4.2B and every `results/v3_review/` package remain denied. Authorization is only the range named in `ACTIVE_SPRINT.md`.

**Code that implements it:** `src/inequality_mechanisms/audits/v4_artifact_guard.py` (`V4_2C_ALLOWED_PACKAGE`, `assert_v4_2c_output_allowed`, `prepare_v4_2c_output_dir`); planning commit landed ADR-031 and the sprint.

**Tests that support it:** `tests/v4/test_v4_2c_artifact_guard.py`.

**Why the test is valid:** Allowed and nested V4.2C paths succeed; historical V4.2B/V3 paths fail closed without mutating predecessor bytes.

**Known failure modes:** A writer that bypasses the guard can still touch disk. Canonical scripts and the packager go through the guard.

**Artifact evidence:** The retained package exists only under the allowed root. V4.2B `files_digest` re-verified during closeout.

**Remaining nonclaims:** The guard does not prove that every future script will call it.

## V4-231 — OMPL Python-binding capability probe

**Claim:** Binding features are probed in spawn children and recorded as `supported`, `unsupported`, `crashed`, `child_timeout`, `missing_symbol`, `binding_exception`, or `unavailable_dependency`. Missing OMPL returns a complete unavailable matrix. Optional PDST remains optional.

**Code that implements it:** `src/inequality_mechanisms/adapters/ompl/capabilities.py`, `scripts/probe_v4_2c_ompl_capabilities.py`.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_capabilities.py`.

**Why the test is valid:** The catalog is complete without importing `ompl`. Injected hang/crash runners type those outcomes. The probe script refuses writes outside the allowed root. OMPL-present runs record a version and required-row completeness.

**Known failure modes:** C++ OMPL warnings can write to stdout; the probe script redirects fd 1 to stderr while probing so stdout remains JSON. `setCellSizes` on this wheel is `(dim, cellSize)`, not a vector; the probe uses `apply_projection_cell_sizes`.

**Artifact evidence:** `capability_matrix.json` in the retained package. Live 2.0.1 matrix: PDST missing, `setStateSamplerAllocator` missing, precomputed sampler unsupported; required planner classes and exact-solution API supported.

**Remaining nonclaims:** A supported construction probe is not a completeness or optimality claim.

## V4-232 — Shared OMPL session and planner-geometry record

**Claim:** One session builds the bounded U space, exact start, finite goals, input-linear validity, and actuator-travel objective. Every row serializes a complete planner-geometry record. PRM/RRTConnect remain compatibility wrappers.

**Code that implements it:** `src/inequality_mechanisms/adapters/ompl/session.py`, `planner_geometry.py`; `planner_base.py` remains the compatibility orchestrator.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_session.py` and existing V3.5 adapter tests.

**Why the test is valid:** Geometry records reject missing fields and illegal projection attachments on primary/control rows. Approximate OMPL paths stay `unsolved`.

**Known failure modes:** Bindings that hang on multi-`GoalStates` are not fixed in the session; they are typed at the worker.

**Artifact evidence:** Every Stage A sample row serializes the eleven ADR-031 geometry fields.

**Remaining nonclaims:** Session reuse does not change U-state identity or local motion.

## V4-233 — RRT*, BIT*, and FMT adapters

**Claim:** Thin wrappers honor only proven binding methods. Exact start, frozen finite goals, exact-solution detection, input-linear validity, and actuator-travel objective are unchanged. FMT is an independent sample-count run, not checkpoint continuation.

**Code that implements it:** `src/inequality_mechanisms/adapters/ompl/rrt_star.py`, `bit_star.py`, `fmt.py`, `binding.py`.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_optimizing_adapters.py`.

**Why the test is valid:** Missing required setters are `OmplBindingRejectedError`. FMT rejects optimizer checkpoints. Capabilities declare FMT non-incremental.

**Known failure modes:** Family metrics that the binding does not expose are `null` with a reason, not zero.

**Artifact evidence:** Stage A/B retain `ompl_rrt_star`, `ompl_bit_star`, and `ompl_fmt` rows.

**Remaining nonclaims:** Lower cost on one row is not a global ranking.

## V4-234 — Normalized U/Q/X KPIECE projections

**Claim:** One KPIECE wrapper and three stable IDs differ only by exploration projection. Q uses mounted coordinates. Cell sizes are explicit. Native follower angles are not the projection.

**Code that implements it:** `src/inequality_mechanisms/adapters/ompl/projections.py`, `kpiece.py`; `apply_projection_cell_sizes` in `binding.py`.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_kpiece_projections.py`.

**Why the test is valid:** Nonprojection config JSON matches across the three IDs. Cell sizes follow `cells_per_axis`. Smoke solves keep exact start and actuator-travel cost when OMPL is present.

**Known failure modes:** The 2.0.1 nanobind API is `setCellSizes(dim, cellSize)`. Occupancy/cell stats are not exposed (`kpiece_cell_stats_not_exposed_by_binding`). Binding-method logs must be JSON-safe; live evaluator objects are recorded as type tags.

**Artifact evidence:** Stage A/B retain `ompl_kpiece_u`, `ompl_kpiece_q`, and `ompl_kpiece_x`.

**Remaining nonclaims:** KPIECE is a diagnostic family, not an optimizer ranking.

## V4-235 / V4-236 — Process worker and checkpoint metrics

**Claim:** One child writes one atomic JSON result. Optional PDST and custom samplers are `unsupported_optional`. RRT*/BIT* may continue cumulatively; FMT does not. Unsupported metrics are null with a reason. Nanobind PRM multi-`GoalStates` hangs remain a labeled sequential envelope.

**Code that implements it:** `src/inequality_mechanisms/benchmarks/ompl_process_worker_v4_2c.py`; checkpoint extraction in adapters/session.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_process_worker.py`.

**Why the test is valid:** Unknown IDs fail closed. Truncated tempfiles are never the completed `--out` path. KPIECE child output is JSON-serializable. PRM rows label `ompl_prm_sequential_goal_states` and `ompl_prm_multi_goalstates_workaround`.

**Known failure modes:** Sequential PRM is not a true multi-goal solve. Process isolation does not prove identical sample sequences across mechanisms.

**Artifact evidence:** Stage directories use per-row JSON plus `attempts/` for crashes/timeouts.

**Remaining nonclaims:** Fresh-process agreement is not in-process RNG reproducibility.

## V4-237 — Staged runner and frozen configs

**Claim:** Smoke, calibration, and audit configs are digest-locked. Audit mode requires a matching `calibration_selection.json`. The runner consumes frozen V4.2B and writes only the V4.2C root. Failed attempts are retained and never marked complete.

**Code that implements it:** `src/inequality_mechanisms/experiments/v4/ompl_planner_portfolio.py`, `ompl_planner_portfolio_config.py`; `configs/v4/ompl_planner_portfolio_{smoke,calibration,audit}_v1.json`; `scripts/generate_v4_2c_ompl_planner_portfolio.py`.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_planner_portfolio.py`.

**Why the test is valid:** Frozen matrix sizes are 32 / 768 / 6200. Audit refuses a missing or mismatched calibration digest. Config extra fields are forbidden.

**Known failure modes:** Stage D / `all_cases_optional` is not implemented. Knobs were not retuned after Stage B.

**Artifact evidence:** Stage A 32/32 completed worker rows; Stage B 768/768 completed worker rows; calibration digest `fef43c8178a408a323eb1b2773b423e848c733b1f82f143409983ef691b8027b`.

**Remaining nonclaims:** Worker `completed` is not the same as planning `success`. Approximate paths stay unsolved.

## V4-238 — Question-grouped report

**Claim:** The report is grouped by scientific question and planner family. HTML has no calculations absent from `summary.json`. There is no cross-family effort ranking or winner table.

**Code that implements it:** `src/inequality_mechanisms/visualization/v4/ompl_planner_portfolio.py`.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_planner_portfolio_report.py`.

**Why the test is valid:** Forbidden tokens (`winner`, `outperform`, `ranking`, `estimand`) are rejected except the allowed nonclaim phrases. `href_targets` checks link integrity. Optional PDST remains visible.

**Known failure modes:** Figures are derived views. Machine-readable rows remain the source of truth.

**Artifact evidence:** Each stage `report/` plus the package landing `index.html`.

**Remaining nonclaims:** The LEDE and no-inference statement are retained on the landing page.

## V4-239 — Retained package, review, and authorization reset

**Claim:** From a clean implementation revision, Stage A/B/C are packaged with compressed extracts, `manifest.json`, and a verifier that checks hashes, frozen counts, HTML links, PDST visibility, and the V4.2B predecessor digest. Docs closeout resets authorization without activating V4.3.

**Code that implements it:** `src/inequality_mechanisms/audits/v4_2c_artifact.py`; `scripts/package_v4_2c_ompl_planner_portfolio.py`; `scripts/verify_v4_2c_artifact.py`.

**Tests that support it:** `tests/v4/test_v4_2c_ompl_planner_portfolio_closeout.py`.

**Why the test is valid:** Synthetic packages verify inventory and PDST visibility. Frozen 32/768/6200 counts reject undersized fixtures. Leftover paths whose names merely contain `v4_2c_ompl_planner_portfolio` are not treated as the allowed package.

**Known failure modes:** §13's drafted `planners/` / `cases/` / `methods/` tree is not the live layout. Stage directories are the source of truth; `calibration/*.jsonl.gz` and `audit/*.jsonl.gz` are derived. Packaging allows untracked files only under the V4.2C package path.

**Artifact evidence:** Recorded in [`V4_2C_OMPL_PLANNER_PORTFOLIO_CLOSEOUT.md`](V4_2C_OMPL_PLANNER_PORTFOLIO_CLOSEOUT.md) after `verify_v4_2c_artifact.py`.

**Remaining nonclaims:** This sprint does not close `V3-DEFER-001`, obstacles, MoveIt, 3R/6R, or V4.3.
