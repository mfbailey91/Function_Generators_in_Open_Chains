# V4.2C Phase 0 — repository preflight

**Date:** 2026-08-23
**Branch:** `Version_4_Kinematic_Transmission_Geometry`
**HEAD:** `a93dab6a4decbfe45a3da2618568993da8884be8`
**Authorization:** none (`ACTIVE_SPRINT.md`; V4.2B completed; V4.3 drafted/blocked)
**This increment:** observational record only. No source, test, config, result, or authorization edits.

Sprint V4.2C remains unauthorized. This note records the post-V4.2B baseline before any later docs landing, activation of V4-230–V4-239, or adapter work.

## Contracts read

Repo (already landed):

- `docs/software/planning/ACTIVE_SPRINT.md`
- `docs/software/planning/sprints/v4/SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md`
- ADR-023 (exact start / goal regions), ADR-024 (local motion and cost), ADR-025 (planner capabilities), ADR-026 (benchmark classification)
- ADR-029 (mounted output coordinates)
- **Existing ADR-030** — paired final topology and nonfinite edge semantics (`ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md`)

Bundle (untracked; read in place, not landed):

- `v4_2c_ompl_planner_portfolio_planning_bundle/SPRINT_V4_2C_OMPL_PLANNER_GEOMETRY_PORTFOLIO.md`
- `v4_2c_ompl_planner_portfolio_planning_bundle/ADR-030-ompl-planner-geometry-contract.md`
- `v4_2c_ompl_planner_portfolio_planning_bundle/V4_2C_CURSOR_IMPLEMENTATION_GUIDE.md`
- `v4_2c_ompl_planner_portfolio_planning_bundle/V4_2C_PATCH_MANIFEST.md`

The bundle ADR-030 is a **different** decision from accepted paired-topology ADR-030. See blockers below.

## V4.2B artifact

Verifier:

```text
PYTHONPATH=src .venv/bin/python scripts/verify_v4_2b_artifact.py \
  results/v4_review/v4_2b_span_controlled_corrective_closeout/
```

Result: **pass**. `n_files=23`, `n_geometry_rows=55539`, `files_digest=ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a`. The canonical package was not mutated.

## OMPL adapter surface (unchanged)

Inspected:

- `src/inequality_mechanisms/adapters/ompl/` — `__init__.py`, `_availability.py`, `state_space.py`, `goals.py`, `objective.py`, `validity.py`, `metrics.py`, `planner_base.py`, `prm.py`, `rrt_connect.py`
- `src/inequality_mechanisms/benchmarks/ompl_process_worker_v3_6.py`
- `src/inequality_mechanisms/benchmarks/ompl_process_worker_v3_7.py` (present; not listed in the Phase 0 guide)

Recorded contract of the current adapter (do not “fix” in Phase 0):

- OMPL state is a bounded `RealVectorStateSpace` over certified **U**.
- Reconstruction is `PhysicalState` via `robot.state_from_input`.
- Local motion required by the adapter is `InputLinearMotion`.
- Objective required by the adapter is `ActuatorTravelObjective`, mapped to OMPL path length as `euclidean_u`.
- Finite goals are `ob.GoalStates`.
- Public planner IDs remain `ompl_prm` and `ompl_rrt_connect`.

### PRM multi-goal workaround

Nanobind OMPL PRM hangs when `GoalStates` size is greater than 1. Both process workers evaluate the frozen represented set with **sequential single-goal solves** and label the row explicitly:

- `ompl_prm_sequential_goal_states`
- `ompl_prm_sequential_attempts`
- `ompl_prm_sequential_successes`
- `ompl_prm_multi_goalstates_workaround`

That envelope is not a true multi-goal PRM solve. Later V4.2C work must keep the label and must not relabel it as one multi-goal query.

## Baseline tests (this machine)

```text
is_ompl_available() = False
ompl_version_string() = None
```

```text
PYTHONPATH=src MPLBACKEND=Agg .venv/bin/python -m pytest -q \
  tests/v3/test_v3_5_ompl_optional_gate.py \
  tests/v3/test_v3_5_ompl_adapter.py
```

**10 passed, 11 skipped** in 0.17s. The optional gate is green without bindings. Adapter tests skip when OMPL is absent. An OMPL-present environment was not available on this host; later phases that add planner wrappers must re-run the same files where bindings exist and record the OMPL version then.

## Docs patch check (not applied)

```text
git apply --check v4_2c_ompl_planner_portfolio_planning_bundle/v4_2c_ompl_planner_portfolio_docs.patch
```

**Failed** (exit 1), as expected against post-V4.2B docs. Rejected hunks:

- `docs/software/V4_PROJECT_PLAN.md`
- `docs/software/architecture/adr/README.md`
- `docs/software/planning/README.md`
- `docs/software/planning/sprints/v4/README.md`

The patch was generated against reviewed base `e98ca1f5c7dcf4e21f40185d36c8ba1a6664bf7b`. Current `sprints/v4/README.md` still says **Do not create V4.2C.** The patch was not applied.

## Blockers for later phases (not resolved here)

1. Bundle ADR-030 collides with accepted paired-topology ADR-030. Future docs landing must number the OMPL planner-geometry decision **ADR-031**.
2. The raw docs patch cannot be applied cleanly. Later landing is a hand-port onto the current tree, not `git apply` of the bundle patch.
3. Activation of V4-230–V4-239 is a **separate** later commit. Phase 0 does not change `ACTIVE_SPRINT.md`.
4. V4.3 remains drafted/blocked and is not activated here.

## Untracked leftovers (not committed)

Left untracked on purpose: `v4_2c_ompl_planner_portfolio_planning_bundle/`, `diagnose_pr28_common_bank_digest.py`, `pr28_ci_3_11_corrective.patch`, `pr28_ci_bundle/`, and Finder `.DS_Store` / `.textClipping` files under the V4.2B package.
