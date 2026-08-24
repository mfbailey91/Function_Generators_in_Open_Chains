# V4.2C Cursor Implementation Guide

## Purpose

This guide turns `SPRINT_V4_2C_OMPL_PLANNER_GEOMETRY_PORTFOLIO.md` into an implementation sequence that Cursor can execute without redefining the sprint.

The sprint document is authoritative for scope, claims, work packages, and exit criteria. Cursor Plan Mode should be used only to plan the current work package with exact files, symbols, tests, and commands.

## Hard authorization gate

Do not begin source work unless all of the following are true:

1. V4.2B is closed and its corrected artifact has passed verification.
2. `ACTIVE_SPRINT.md` has returned to no authorization.
3. A separate activation commit authorizes **V4-230–V4-239 only**.
4. The implementation branch starts from the reviewed post-V4.2B revision.

The planning patch intentionally does not modify `ACTIVE_SPRINT.md`.

## Nonnegotiable invariants

Preserve throughout:

```text
physical state identity = U + complete PhysicalState
mounted robot coordinate = Q from ADR-029
OMPL primary state space = bounded RealVectorStateSpace over U
local motion = InputLinearMotion
objective = ActuatorTravelObjective / exact Euclidean-U path length
start = exact physical start
goal = frozen finite physical goal set
success = exact OMPL solution satisfying the physical predicate
approximate OMPL path = unsolved
predecessor artifacts = immutable
```

No work package may silently change these while adding a planner.

## Recommended commit structure

1. `docs(v4.2c): land planner-geometry contract` — planning/ADR/index only.
2. `feat(v4.2c): add OMPL capability matrix and shared session` — V4-231/V4-232.
3. `feat(v4.2c): add RRTstar BITstar and FMT adapters` — V4-233.
4. `feat(v4.2c): add normalized U Q X KPIECE projections` — V4-234.
5. `feat(v4.2c): add process workers sampling gates and metrics` — V4-235/V4-236.
6. `feat(v4.2c): add staged runner and report` — V4-237/V4-238.
7. `results(v4.2c): retain planner portfolio artifact` — generated evidence only.
8. `docs(v4.2c): close sprint and reset authorization` — closeout/no authorization.

Do not mix generated evidence into the implementation commit.

## Phase 0 — repository preflight

### Read first

```text
docs/software/planning/ACTIVE_SPRINT.md
docs/software/planning/sprints/v4/SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md
docs/software/planning/sprints/v4/SPRINT_V4_2C_OMPL_PLANNER_GEOMETRY_PORTFOLIO.md
docs/software/architecture/adr/ADR-023-v3-exact-start-and-goal-regions.md
docs/software/architecture/adr/ADR-024-v3-local-motion-and-cost.md
docs/software/architecture/adr/ADR-025-v3-planner-capabilities-and-adapters.md
docs/software/architecture/adr/ADR-026-v3-benchmark-classification-and-metrics.md
docs/software/architecture/adr/ADR-029-mounted-output-coordinate.md
docs/software/architecture/adr/ADR-031-ompl-planner-geometry-contract.md
```

### Inspect current code

```text
src/inequality_mechanisms/adapters/ompl/__init__.py
src/inequality_mechanisms/adapters/ompl/state_space.py
src/inequality_mechanisms/adapters/ompl/goals.py
src/inequality_mechanisms/adapters/ompl/objective.py
src/inequality_mechanisms/adapters/ompl/validity.py
src/inequality_mechanisms/adapters/ompl/metrics.py
src/inequality_mechanisms/adapters/ompl/planner_base.py
src/inequality_mechanisms/adapters/ompl/prm.py
src/inequality_mechanisms/adapters/ompl/rrt_connect.py
src/inequality_mechanisms/benchmarks/ompl_process_worker_v3_6.py
```

### Baseline commands

Run the existing optional gate and adapter tests both without and with the OMPL environment where available. Record the exact baseline, OMPL version, and known PRM multi-goal workaround before editing.

## Phase 1 — V4-230 contract and guard

### Goal

Create the new artifact boundary before any generator exists.

### Actions

- Add the V4.2C root to `v4_artifact_guard.py` only after activation.
- Add source-digest verification for V4.2B.
- Add guard tests using `tmp_path`.
- Prove frozen result roots remain denied.

### Review questions

- Can any new code write to V4.2B or a V3 result package?
- Does a nested valid V4.2C path work?
- Is `ACTIVE_SPRINT.md` still the only source of authorization?

## Phase 2 — V4-231 capability probe

### Goal

Determine the actual OMPL 2.0.1 Python surface before designing wrappers around C++ documentation.

### Implement

```text
src/inequality_mechanisms/adapters/ompl/capabilities.py
scripts/probe_v4_2c_ompl_capabilities.py
tests/v4/test_v4_2c_ompl_capabilities.py
```

### Probe each feature in a child process

- planner class construction;
- required setter/getter presence;
- true multi-GoalStates solve;
- repeated solve continuation;
- Python projection evaluator subclass or callback;
- explicit projection bounds/cell sizes;
- PlannerData and progress properties;
- state sampler allocator and precomputed/deterministic sampler;
- exact-solution API.

### Output

A complete JSON matrix with:

```text
supported
unsupported
crashed
child_timeout
missing_symbol
binding_exception
```

Do not let one feature probe crash the parent or block the rest of the matrix.

## Phase 3 — V4-232 shared session refactor

### Goal

Remove the one-shot assumptions from `planner_base.py` while preserving PRM/RRTConnect behavior.

### Sequence

1. Add `PlannerGeometryRecord` with strict canonical values.
2. Extract session construction: space, SI, validators, finite goals, objective, start, counters.
3. Extract final result assembly.
4. Add one-shot and checkpointed solve functions.
5. Keep `solve_with_ompl_planner` as a compatibility wrapper until old call sites are migrated.
6. Re-run all V3 OMPL tests before adding a new planner.

### Stop condition

Do not continue if any existing planner ID, task classification, exact-start behavior, candidate provenance, cost, or optional-dependency behavior changes unexpectedly.

## Phase 4 — V4-233 optimizing adapters

Implement one planner at a time in this order:

### 4A. RRT*

Why first: closest extension of the existing RRT tree family.

Required checks:

- parameter resolution and provenance;
- exact finite goal handling;
- checkpoint continuation;
- cost nonincrease across checkpoints;
- direct-reference gap.

### 4B. FMT

Why second: fixed-sample behavior is easier to separate from anytime time budgets.

Required checks:

- independent sample-count ladder;
- effective sample count;
- nearest-K/radius mode;
- heuristics on/off labels;
- no false continuation semantics.

### 4C. BIT*

Why third: combines informed ordering, batching, and rewiring and benefits from the session/checkpoint infrastructure already tested.

Required checks:

- samples per batch;
- queue/pruning settings;
- repeated solve continuation;
- exact best-cost checkpoints;
- no hidden custom objective.

After each planner, add it lazily to `adapters/ompl/__init__.py` and run the entire old/new OMPL test set.

## Phase 5 — V4-234 KPIECE projections

### Implement projection strategies first

```text
normalized_u
normalized_mounted_q
normalized_cartesian_x
```

Test them independently of KPIECE.

### Then add KPIECE wrapper

One wrapper accepts a typed projection strategy. Stable public planner IDs remain separate:

```text
ompl_kpiece_u
ompl_kpiece_q
ompl_kpiece_x
```

### Factor-isolation test

Serialize the fully resolved config for all three conditions, remove the projection fields, and require byte-identical canonical JSON. This proves the ablation changes only projection.

### Visual check

For one shared physical path, plot the same sampled states in normalized U, normalized Q, and normalized X. The plot is a diagnostic test artifact, not retained scientific evidence yet.

## Phase 6 — V4-235/V4-236 process and metrics

### Process worker

Replace the V3.6 planner `if/elif` chain with a registry:

```python
PLANNER_FACTORIES: dict[str, PlannerFactory]
```

One worker request contains the complete resolved planner config. One child writes one atomic response.

### Checkpoint semantics

- RRT*/BIT*: cumulative in one child process.
- FMT: independent run per sample count.
- KPIECE/PRM/RRTConnect/optional PDST: one calibrated budget.

### Missing internals

Do not infer internal queue, cell, or rewiring counts from final paths. Serialize `null` plus `unavailable_reason` when the binding does not expose a property.

### Optional work ordering

PDST and custom/precomputed samplers are last. Do not touch them until required planners, KPIECE, workers, and checkpoint metrics are green.

## Phase 7 — V4-237 staged runner

### Config discipline

- strict Pydantic models;
- `extra="forbid"` at every level;
- source V4.2B digest required;
- resolved range/cell/budget parameters written before execution;
- no outcome-dependent case or task replacement.

### Modes

```text
smoke
calibration
audit
all_cases_optional
```

Audit refuses to run until a frozen calibration-selection file exists and matches the config digest.

### Resume discipline

A row is complete only when:

- the child exited successfully;
- atomic output parses;
- request digest matches;
- result schema validates;
- expected planner/task/mechanism/repetition IDs match.

Retain failed attempts; do not silently retry them into invisibility.

## Phase 8 — V4-238 report

Build report sections in the sprint order, not planner-name order.

The first visible statement on the root page should explain:

- U is authoritative;
- free-space direct reference is available;
- different planner families expose different metrics;
- the report is descriptive and not a global ranking.

Required source-of-truth files are the compressed rows and manifest. HTML may not contain calculations that cannot be regenerated from machine-readable data.

## Phase 9 — V4-239 closeout review

Review every work package using this format:

```text
Claim:
Code that implements it:
Tests that support it:
Why the test is valid:
Known failure modes:
Artifact evidence:
Remaining nonclaims:
```

Then:

1. generate evidence from a clean implementation revision;
2. verify manifest and predecessor digests;
3. inspect representative successes, failures, and unsupported rows;
4. commit evidence separately;
5. write closeout note;
6. reset authorization to none;
7. do not activate V4.3 in the same change.

## Cursor prompts by work package

### V4-231

> Read the V4.2C sprint and ADR-031. Implement only the OMPL Python-binding capability matrix in fresh child processes. Do not add planner wrappers yet. Preserve optional import behavior. Return exact files changed, probe cases, tests, commands, and unsupported features.

### V4-232

> Refactor the current OMPL one-shot solve path into a reusable session and finalizer while keeping PRM and RRTConnect behavior byte/schema compatible where specified. Add `PlannerGeometryRecord`. Do not add new planners until all old OMPL tests pass.

### V4-233

> Add thin OMPL RRT*, FMT, and BIT* wrappers in that order using the shared session. Honor only binding methods proven by the capability matrix. Preserve exact start, frozen finite goals, exact-solution detection, input-linear validity, and actuator-travel objective. Add family-specific tests and lazy exports.

### V4-234

> Implement normalized U, mounted-Q, and Cartesian-X projection evaluators and one geometric KPIECE wrapper with three stable planner IDs. Prove the three conditions differ only by projection fields. Use explicit bounds and cell sizes; never use native follower angles.

### V4-235/V4-236

> Add a registry-based fresh-process worker and checkpoint metrics. RRT*/BIT* continue cumulatively; FMT uses independent sample-count runs. Record unsupported metrics as null with a reason. Optional PDST and frozen samplers come only after required paths are green.

### V4-237/V4-238

> Add strict smoke/calibration/audit configs, a digest-locked staged runner consuming V4.2B, and a report grouped by scientific question. Preserve every failure row and never emit a global cross-family effort ranking.

## Final do-not-do list

- Do not edit or regenerate V4.2B.
- Do not modify V3 evidence.
- Do not change U-state identity, local motion, objective, start, or physical goal predicate.
- Do not disable direct edges.
- Do not tune planner parameters separately by mechanism.
- Do not hide multi-goal workarounds.
- Do not claim missing metrics are zero.
- Do not implement obstacles, MoveIt, 3R, 6R, dynamics, or trajectory optimization.
- Do not implement optional PDST/sampler work ahead of the required portfolio.
- Do not activate V4.3 during V4.2C closeout.
