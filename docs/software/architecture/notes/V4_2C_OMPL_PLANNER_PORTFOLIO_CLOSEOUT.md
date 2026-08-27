# V4.2C OMPL planner-portfolio closeout

**Disposition:** completed after Stage A/B/C packaging and verification; V4.3 remains drafted / blocked
**Implementation revision:** `5320d6f336ef82615a51f7826d0febd39c18f9db`
**Package:** [`results/v4_review/v4_2c_ompl_planner_portfolio/`](../../../../results/v4_review/v4_2c_ompl_planner_portfolio/)
**Work packages closed:** V4-230 through V4-239
**Work-package review:** [`V4_2C_IMPLEMENTATION_REVIEW.md`](V4_2C_IMPLEMENTATION_REVIEW.md)
**Plot guide / V4.2C-R:** [`V4_2C_CLOSEOUT_REVIEW_AND_PLOT_GUIDE.md`](V4_2C_CLOSEOUT_REVIEW_AND_PLOT_GUIDE.md); derived package [`results/v4_review/v4_2c_r_frozen_data_report/`](../../../../results/v4_review/v4_2c_r_frozen_data_report/)
**No-inference:** OMPL planner-geometry portfolio; descriptive only; no mechanism performance inference.

## What closed

Sprint V4.2C added an explicit planner-geometry contract on the unchanged Version 3 physical problem: authoritative U, input-linear local motion, actuator-travel objective, exact start, and a frozen finite physical goal set. RRT*, BIT*, FMT, and KPIECE-U/Q/X consume that problem. PRM and RRTConnect remain architecture controls. Optional PDST was not run.

Retained evidence was generated from implementation revision `5320d6f3` using CPython 3.13.15 and the `ompl==2.0.1` nanobind wheel. The project `.venv` is CPython 3.14 and cannot install that wheel; that is environment provenance, not a planner ranking.

## Frozen matrix and predecessor

| Stage | Mode | Frozen `n_rows` | Worker completed (pre-package) |
| --- | --- | ---: | --- |
| `stage_a` | smoke | 32 | 32/32, 0 attempts |
| `stage_b` | calibration | 768 | 768/768, 0 attempts |
| `stage_c` | audit | 6200 | 6200/6200, 0 attempts |

Calibration selection is digest-locked to

```text
fef43c8178a408a323eb1b2773b423e848c733b1f82f143409983ef691b8027b
```

Stage B occupancy-health review: every required planner produced completed worker rows on both mechanisms before paired outcomes were treated as audit input. KPIECE occupancy counters remain `null` with `kpiece_cell_stats_not_exposed_by_binding`. Knobs were not retuned.

V4.2B predecessor re-check:

```text
files_digest=ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a
n_files=23
n_geometry_rows=55539
```

Verified V4.2C package:

```text
source_git_revision=5320d6f336ef82615a51f7826d0febd39c18f9db
source_git_dirty=false
files_digest=99ec523a706632391c85e16cae505e6cd11a6f14d15682eb711515aefcf76c93
n_files=7047
n_rows_stage_a=32
n_rows_stage_b=768
n_rows_stage_c=6200
```

Stage C worker rows are 6200/6200 `completed` with planning `success` on this free-space bank. That occupancy is descriptive of the certified actuator box and is not a ranking, unreachability proof, or obstacle-routing result.

## Binding surface (OMPL 2.0.1)

Supported required probes include PRM, RRTConnect, RRT*, BIT*, FMT, KPIECE1, multi-goal construction for the required families, repeated solve, projection evaluators, PlannerData, and the exact-solution API.

Typed gaps retained in `capability_matrix.json`:

| Feature | Status | Detail |
| --- | --- | --- |
| `planner_pdst` / `methods_pdst` | `missing_symbol` | `ompl.geometric.PDST` absent |
| `sampler_allocator` | `missing_symbol` | `setStateSamplerAllocator` absent |
| `sampler_precomputed` | `unsupported` | no precomputed sampler class |
| projection cell sizes | `supported` | live signature `setCellSizes(dim, cellSize)` |

Nanobind PRM still hangs on `GoalStates` size greater than one. The V4.2C worker keeps the sequential single-goal envelope and labels `ompl_prm_sequential_goal_states` plus `ompl_prm_multi_goalstates_workaround`. That envelope is not a true multi-goal PRM query.

## Layout deviation from sprint §13

The drafted tree imagined package-root `resolved_config.json`, `planners/`, `cases/`, and `methods/`. The shipped runner writes `stage_a/`, `stage_b/`, and `stage_c/` with per-row JSON, `request_matrix.json`, `progress.json`, and stage reports. Closeout treats those stage directories as the source of truth. Compressed jsonl files under `calibration/` and `audit/` are derived views hashed in `manifest.json`. Optional PDST remains visible in HTML without a `pdst_optional/` planner tree.

## §4.4 nonclaims (all retained)

V4.2C does not claim:

- that one planner is universally best;
- that one mechanism universally makes planning easier;
- that a graph expansion, tree vertex, batch sample, projection cell, and wall-clock second are interchangeable effort units;
- that free-space behavior predicts obstacle-routing performance;
- that finite-time failure proves unreachability;
- that optional PDST results establish complete independence from metric or projection choices;
- that this sprint closes the deferred native-planner backlog.

Free space here is a planner-semantics, convergence, and projection-sensitivity diagnostic. It is not obstacle routing.

Stage D / `all_cases_optional` was not run.

## V4.2C-R frozen-data report clarification

A later presentation follow-up re-read frozen Stage C rows and wrote sibling figures under [`results/v4_review/v4_2c_r_frozen_data_report/`](../../../../results/v4_review/v4_2c_r_frozen_data_report/). It did not rerun OMPL, change the estimand, or mutate the V4.2C `files_digest`. See the [plot guide](V4_2C_CLOSEOUT_REVIEW_AND_PLOT_GUIDE.md).

## Authorization

`ACTIVE_SPRINT.md` returns to **no code authorization**. Activating Sprint V4.3, residual V3.7, obstacles, MoveIt, 3R/6R, or native OMPL clones requires a separate reviewed change. V4.2C completion does not authorize later sprints.
