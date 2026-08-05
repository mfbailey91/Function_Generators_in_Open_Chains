# Sprint V2.10 — Production Monte Carlo Orchestration: Dijkstra Campaign

## Theme

> Scale one trusted search process without turning the laptop into part of the experiment.

## Status and dependency

**Status:** Completed — evidence in [V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md](../../../experiments/reports/V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md)
**Issue slug:** `production_monte_carlo_orchestration_v2_9`
**Blocked by:** Review of Sprint V2.8 shared-Q evidence and Sprint V2.9 U-distance-only diagnostic
**Solver scope:** Dijkstra only
**Frozen production objective:** `actuator_travel` (raw Euclidean actuator distance; no \(Q\) term, \(\alpha\), or planner-side normalization)
**Execution target:** User’s Apple M4 Pro Mac, with hardware discovered and benchmarked at runtime rather than assumed from the chip family name

**Related project note:** [Sequenced Search-Algorithm Expansion](../../../architecture/notes/PROJECT_NOTE_FUTURE_SEARCH_ALGORITHMS.md)

This sprint was originally sketched as V2.9 while V2.8 was current. The U-distance diagnostic later took the V2.9 number. Work-package IDs remain `V2-901`–`V2-912`.

## Objective

Build a restartable, memory-bounded, scientifically reproducible Monte Carlo system for the Version 2 paired mechanism study. Run one solver—Dijkstra—over a large and varied mechanism/task population while preserving the accepted Version 2 graph, mechanism, objective, task, and result semantics.

The sprint converts the existing diagnostic experiment architecture into a production compute workflow. It does not add a solver comparison. A* and sampling-based planners are explicitly deferred to later campaigns that will reuse the frozen Dijkstra sample bank.

## Sprint question

> Across a broad population of certified monotonic four-bar mechanisms, span-matched gearbox controls, and matched output-space tasks, what distribution of search-effort and path effects appears under Dijkstra, and how much mechanism and task variation is required to estimate that distribution precisely?

## Central execution decision

### One graph solver at a time

Every V2.10 production config contains exactly:

```yaml
search:
  algorithm: dijkstra
```

The runner rejects algorithm lists and does not run A* after Dijkstra inside the same trial or run package.

“One solver at a time” applies at two levels:

1. **Scientific level:** one solver family per immutable Monte Carlo campaign.
2. **Machine-safety default:** one active search process at a time (`workers: 1`) until profiling demonstrates that a higher worker count is safe and useful.

Optional parallelism may be enabled only after deterministic equivalence and resource calibration. It changes throughput, not trial semantics.

## Research role of Dijkstra

Dijkstra is the explanatory reference because it evaluates the accepted weighted graph without heuristic steering. The production campaign will use it to characterize:

- the size and shape of the reachable cost basin;
- paired four-bar versus gearbox expansion effects;
- path-cost and path-geometry effects;
- correlations between mechanism descriptors and search effort;
- between-mechanism versus within-mechanism variance;
- stability with graph resolution and sample count.

This sprint does not claim Dijkstra is the eventual practical planner.

## Accepted prerequisites inherited from V2.8 / V2.9

V2.10 must reuse or explicitly supersede the reviewed V2.8 / V2.9 decisions for:

- certified monotonic operating branches;
- shared output-space graph semantics;
- span-matched affine gearbox controls;
- exact output-space task overlays;
- graph-invariant checks inside each mechanism pair;
- the accepted primary edge objective (`actuator_travel`) and reporting-only \(U\) normalization;
- the accepted graph resolution or its production calibration method;
- deterministic IDs, serialization, and local HTML result packages.

The production sprint must not silently reopen these questions while scaling.

## Experimental design

### Hierarchical sample structure

The production population is hierarchical:

\[
M\ \text{mechanism pairs}
\times
K\ \text{tasks per mechanism pair}.
\]

Tasks nested within one mechanism are repeated observations, not independent mechanism samples. Analysis must first preserve the mechanism grouping and must not treat all task rows as independent draws.

### Initial cardinality targets

The implementation must support the following staged defaults:

| Stage | Mechanism pairs | Tasks per pair | Purpose |
| --- | ---: | ---: | --- |
| Smoke | 2 | 2 | schema, resume, and shard verification |
| Hardware calibration | 8 | 4 | time and peak-memory measurement |
| Variance pilot | 50 | 8 | estimate within- and between-mechanism variance |
| Production minimum | 100 | accepted production K | minimum inferential population |
| Production batch | 25 additional | accepted production K | sequential precision updates |
| Production cap | 500 | accepted production K | bounded worst-case campaign |

The initial candidate range for the accepted production task count is:

\[
K\in\{8,12,16\}.
\]

The variance pilot selects the smallest value whose mechanism-level estimates are sufficiently stable. The selected value is recorded as a run decision, not left as an implicit default.

### Task bank

Tasks should be generated in normalized output coordinates and mapped into each pair’s shared output box. The production task bank should cover:

- short, medium, and long output displacement;
- joint-1-dominant and joint-2-dominant motion;
- diagonal motion;
- interior and near-boundary endpoints;
- multiple directions through the output box.

Task templates must be versioned independently of mechanisms. A task failure is recorded and must not be silently moved or resampled inside the production runner.

### Mechanism population

Mechanism generation and expensive search execution are separate phases.

The mechanism-bank builder should:

1. generate a large inexpensive candidate pool using mechanism kinematics and branch certification;
2. compute pre-search descriptors;
3. reject invalid, degenerate, or poorly conditioned branches using accepted thresholds;
4. select a broad, reproducible population across descriptor space;
5. freeze mechanism IDs and serialized definitions before production search begins.

Selection descriptors may include:

- follower/output span;
- mean, minimum, maximum, and variance of \(|dq/du|\);
- variation of \(\log |dq/du|\);
- fraction of the branch near low gain;
- gain asymmetry;
- per-axis descriptor differences;
- branch conditioning margins.

Mechanisms must not be selected using their observed Dijkstra outcome.

## One-mechanism work unit

The atomic production job is one mechanism pair.

For one pair, the worker must:

1. load the frozen four-bar and span-matched gearbox definitions;
2. build or load the shared output topology;
3. attach both mechanism embeddings and edge-cost data;
4. assert pair graph invariants;
5. execute all accepted tasks serially with Dijkstra;
6. write one complete mechanism-pair shard;
7. atomically mark the pair complete;
8. release graph and search memory before loading the next pair.

The runner must not parallelize individual tasks inside one mechanism pair in V2.10.

## M4 Pro execution profile

“M4 Pro” identifies the chip family but not the exact CPU configuration or unified-memory capacity. The runner must capture the actual machine environment at calibration and production time.

### Required environment capture

Record at minimum:

- macOS version;
- Python version and executable;
- package lock or installed dependency versions;
- Git revision and dirty-tree status;
- processor/chip description;
- physical and logical CPU counts exposed by the OS;
- total unified memory;
- available memory at run start when obtainable;
- process start method;
- numerical-library thread environment;
- runner worker count;
- graph resolution and expected node/edge counts.

A macOS helper may gather hardware fields from commands such as:

```bash
system_profiler SPHardwareDataType
sysctl -n hw.physicalcpu
sysctl -n hw.logicalcpu
sysctl -n hw.memsize
```

Command availability and parse failures must be handled without aborting the scientific run; missing fields are stored as unavailable.

### Default execution policy

Production defaults:

```yaml
execution:
  workers: 1
  tasks_parallel_within_mechanism: false
  numerical_threads_per_worker: 1
  checkpoint_unit: mechanism_pair
  atomic_shards: true
  resume: true
```

The launcher should set or recommend:

```bash
OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1
VECLIB_MAXIMUM_THREADS=1
NUMEXPR_NUM_THREADS=1
```

### Optional worker calibration

After the serial calibration passes, the benchmark may compare `workers = 1, 2, 4` on the same small frozen workload.

A higher worker count may become an accepted local run profile only when:

- trial outputs are byte-equivalent except for permitted runtime/environment fields;
- throughput improves materially;
- peak aggregate memory remains below the configured safety threshold;
- the OS remains responsive during a sustained calibration interval;
- no worker performs nested numerical threading.

The production config remains explicit about the accepted worker count. The project must never infer “use all cores.”

## Resource-safety contract

### Memory

The calibration runner records peak resident memory per mechanism-pair work unit. The production preflight estimates aggregate memory from:

\[
R_{\mathrm{estimated}}
=
R_{\mathrm{parent}}
+
W R_{\mathrm{worker,peak}}
+
R_{\mathrm{margin}},
\]

where \(W\) is the configured worker count.

The run must refuse to start or require an explicit override when the estimate exceeds the configured fraction of total memory.

Suggested default safety policy:

```yaml
execution:
  max_estimated_memory_fraction: 0.65
  require_override_above_limit: true
```

This is a safety threshold, not a claim about exact macOS memory behavior.

### Runtime and interruption

- Checkpoint after every mechanism pair.
- Handle `SIGINT` by finishing or safely abandoning the current temporary shard.
- Never rewrite completed shards during resume.
- Print completed, failed, excluded, pending, and elapsed counts at bounded intervals.
- Do not retain every trial result, graph, or figure in memory.

### Visualization

Production search and visualization are separate phases.

During the Dijkstra campaign:

- write numerical records and a small bounded set of diagnostic samples;
- do not render a plot for every task;
- do not build the full HTML canvas until requested after simulation;
- retain enough IDs and paths to regenerate accepted visualizations.

## Storage and resume architecture

### Run layout

```text
results/<run_id>/
├── manifest.json
├── config.snapshot.yaml
├── environment.json
├── sample_bank.json
├── progress.json
├── shards/
│   ├── mechanism_000000.jsonl
│   ├── mechanism_000001.jsonl
│   └── ...
├── failures/
│   ├── mechanism_000137.json
│   └── ...
├── merged/
│   ├── trials.jsonl
│   ├── mechanism_summary.jsonl
│   └── summary.json
└── reports/
    ├── precision.json
    ├── exclusions.json
    └── index.html
```

### Atomic shard lifecycle

```text
pending -> running -> completed | excluded | failed
```

A worker writes:

```text
shards/.mechanism_000042.tmp
```

and renames it atomically to:

```text
shards/mechanism_000042.jsonl
```

only after all tasks and required summary records for that mechanism pair are complete.

### Resume semantics

On resume:

- completed shards are immutable and skipped;
- failed or excluded pairs remain recorded unless an explicit retry policy is selected;
- a stale temporary shard is quarantined or overwritten only after validation;
- the sample bank, config digest, code revision policy, solver ID, and schema version must match;
- a mismatch starts a new run rather than silently mixing campaigns.

## Result schema

Every trial record includes at minimum:

- run ID;
- sample-bank version and digest;
- mechanism-pair ID;
- mechanism type;
- task ID;
- graph ID and resolution;
- solver ID (`dijkstra`);
- objective ID and parameters;
- start and goal states;
- graph invariant status;
- task feasibility status;
- expanded, generated, reopened, and stale counts;
- reachable-node count and expansion fraction;
- optimal total cost;
- raw objective components;
- path node and edge counts;
- \(L_U, L_Q, L_X\);
- runtime as a secondary implementation metric;
- peak process memory when measured;
- exclusion or failure code.

Solver metadata must be explicit:

```json
{
  "solver_id": "dijkstra",
  "solver_schema_version": 1,
  "heuristic_id": null
}
```

## Statistical analysis

### Primary paired effect

A default expansion effect may use:

\[
d_{m,k}
=
\log\!\left(
\frac{N_{\mathrm{expanded,FB},m,k}+1}
     {N_{\mathrm{expanded,GB},m,k}+1}
\right).
\]

Task-level effects are aggregated within mechanism pair before population-level inference.

### Required summaries

- mechanism-level mean or median paired effect;
- hierarchical bootstrap confidence interval;
- within-mechanism and between-mechanism variance estimates;
- task-category effects;
- effect versus mechanism-descriptor relationships;
- normalized expansion effect;
- path-cost and path-quality effects beside expansion effects;
- exclusions and failure-rate summaries.

### Sequential precision review

After each completed production batch, produce—but do not automatically reinterpret—the current estimate, confidence interval, and convergence history.

Initial configurable stopping policy:

```yaml
stopping:
  minimum_mechanisms: 100
  batch_size: 25
  maximum_mechanisms: 500
  confidence_level: 0.95
  target_ci_half_width_log_ratio: 0.05
  stable_batches_required: 3
  max_relative_estimate_change: 0.05
```

The runner may stop launching new batches only when all enabled criteria pass. The final report must show the full precision path so optional stopping is transparent.

## Resolution policy

V2.10 must not run every production mechanism over every grid size.

Use three separate modes:

1. **Resolution calibration** — representative subset over the accepted candidate resolutions.
2. **Production** — one frozen resolution.
3. **High-resolution confirmation** — representative fixed subset at the next higher practical resolution.

The calibration follows the accepted project principles:

- sign stability of the primary effect;
- bounded change relative to the next higher resolution;
- connected-component stability;
- task-feasibility stability;
- recorded grid-anisotropy limitation.

If the Version 2 objective or topology invalidates an earlier resolution decision, record a new decision rather than silently borrowing it.

## Work packages

### V2-901 — Freeze the production research contract

- Record the accepted V2.8 mechanism, task, graph, objective, and comparison semantics.
- Select exactly one production objective.
- Select the resolution-calibration policy.
- Define the primary and secondary Dijkstra outcomes.
- Link the future-search-algorithms project note.

### V2-902 — Add a single-solver production configuration contract

- Require one `search.algorithm` scalar.
- Reject solver arrays.
- Require `dijkstra` for V2.10 science configs.
- Add execution, sharding, resume, memory-safety, and stopping sections.
- Version and validate the config schema.

### V2-903 — Build and freeze the hierarchical sample bank

- Separate mechanism generation from search execution.
- Generate and certify the candidate population.
- Extract pre-search mechanism descriptors.
- Select broad deterministic coverage without using Dijkstra outcomes.
- Create normalized task templates and stable IDs.
- Store sample-bank digest and provenance.

### V2-904 — Implement mechanism-pair work units

- Reuse one shared output topology within each pair.
- Execute all tasks serially.
- Keep only one active Dijkstra search per worker.
- Release graph/search memory between pairs.
- Make work-unit output deterministic.

### V2-905 — Implement atomic sharding and resume

- Add manifest and pair-state lifecycle.
- Add temporary-file and atomic-rename behavior.
- Skip immutable completed shards.
- Validate config, sample-bank, solver, and schema digests on resume.
- Add controlled retry semantics.

### V2-906 — Add M4 Pro hardware calibration and safety preflight

- Capture actual macOS hardware and environment data.
- Measure serial time and peak memory on a frozen calibration bank.
- Implement memory estimate and start refusal/override.
- Verify single numerical thread per worker.
- Optionally compare 1, 2, and 4 workers without changing science outputs.
- Store the accepted local execution profile.

### V2-907 — Remove production scaling traps

- Stream or shard results instead of accumulating the full campaign in memory.
- Avoid repeated scans through all prior trial rows.
- Cache reusable graph topology and static edge data inside a work unit.
- Replace repeated reachability searches with accepted component/preimage checks where semantics permit.
- Bound diagnostic path retention.

### V2-908 — Run resolution and task-count calibration

- Run the representative resolution subset.
- Evaluate candidate \(K\in\{8,12,16\}\).
- Freeze production resolution and tasks per mechanism.
- Record rejected alternatives and decision thresholds.

### V2-909 — Run the Dijkstra variance pilot

- Execute 50 mechanism pairs.
- Produce hierarchical variance estimates.
- Verify shard/resume integrity under interruption.
- Review failure and exclusion mechanisms.
- Confirm production storage and dashboard regeneration cost.

### V2-910 — Run sequential production batches

- Start at the minimum accepted production population.
- Add mechanism pairs in fixed batches.
- Recompute precision summaries after each batch.
- Stop only under the configured transparent rule or the hard cap.
- Never redraw previous mechanisms or tasks.

### V2-911 — Run high-resolution confirmation

- Select a fixed representative 10–20% subset before viewing confirmation outcomes.
- Run at the next higher practical resolution.
- Compare sign, effect magnitude, feasibility, and descriptor relationships.
- Escalate to a larger confirmation only if acceptance criteria fail.

### V2-912 — Merge, analyze, and generate the production report

- Merge immutable shards into analysis tables.
- Generate hierarchical confidence intervals and convergence plots.
- Report mechanism/task variance and descriptor relationships.
- Generate a local HTML canvas from stored data.
- Separate scientific conclusions from M4 Pro runtime observations.
- Freeze the accepted sample bank for the later A* campaign.

## Configuration sketch

```yaml
architecture_version: 2
study:
  name: production_monte_carlo_dijkstra
  sample_bank: configs/v2/sample_banks/production_v1.json

search:
  algorithm: dijkstra

execution:
  workers: 1
  tasks_parallel_within_mechanism: false
  numerical_threads_per_worker: 1
  checkpoint_unit: mechanism_pair
  atomic_shards: true
  resume: true
  max_estimated_memory_fraction: 0.65
  require_override_above_limit: true

population:
  smoke_mechanisms: 2
  calibration_mechanisms: 8
  variance_pilot_mechanisms: 50
  minimum_production_mechanisms: 100
  maximum_production_mechanisms: 500
  production_batch_size: 25
  candidate_tasks_per_mechanism: [8, 12, 16]

stopping:
  confidence_level: 0.95
  target_ci_half_width_log_ratio: 0.05
  stable_batches_required: 3
  max_relative_estimate_change: 0.05

visualization:
  production_path_samples: 5
  render_during_search: false
  generate_canvas_after_run: true
```

The accepted objective is `actuator_travel` from the V2.9 diagnostic. Resolution, mechanism filters, and the production task count \(K\) are recorded from calibration. They must not be guessed silently by the orchestration layer after calibration.

## Verification commands

Target command family:

```bash
pytest tests/experiments_v2 tests/search tests/graphs_v2
python scripts/run_v2_production.py --config configs/v2/production_dijkstra_smoke.yaml
python scripts/run_v2_production.py --config configs/v2/production_dijkstra_calibration.yaml
python scripts/run_v2_production.py --config configs/v2/production_dijkstra.yaml --resume
python scripts/merge_v2_production.py --run results/<run_id>
python scripts/generate_v2_canvas.py --run results/<run_id>
pytest
ruff check .
ruff format --check .
mypy src
```

## Required tests

### Configuration

- solver list is rejected;
- any solver other than Dijkstra is rejected by V2.10 science configs;
- execution and stopping limits validate;
- sample-bank digest mismatch rejects resume.

### Determinism

- serial reruns produce identical scientific records;
- calibrated multi-worker mode matches serial scientific records;
- task order does not change results;
- shard merge order does not change summaries.

### Sharding and recovery

- interruption leaves no completed corrupt shard;
- completed shard is not rewritten on resume;
- stale temporary shard is handled deterministically;
- retry policy preserves original failure records;
- merge detects duplicate or missing mechanism IDs.

### Resource safety

- memory preflight rejects an unsafe synthetic profile;
- explicit override is recorded;
- thread-environment capture works when variables are missing;
- large mock campaigns do not accumulate all graph objects or trial rows.

### Scientific invariants

- paired mechanisms share the accepted output topology;
- exact query states remain matched;
- Dijkstra optimality and expansion semantics match existing regression fixtures;
- task and mechanism IDs survive shard/merge round trips;
- hierarchical aggregation preserves the mechanism grouping.

## Non-goals

- No A* execution in the V2.10 production runner.
- No bidirectional search.
- No PRM, RRT, OMPL, or sample-based planner dependency.
- No simultaneous solver factorial.
- No full cost-family or resolution factorial over the production population.
- No task-level independence assumption.
- No mechanism optimization using production outcomes.
- No dynamics, collision checking, energy model, or reinforcement learning.
- No claim that fewer Dijkstra expansions alone imply a better mechanism.

## Sprint exit criteria

1. V2.8 / V2.9 evidence has been reviewed and one production objective (`actuator_travel`) is frozen.
2. One scalar Dijkstra solver is enforced by configuration and result schema.
3. A versioned hierarchical mechanism/task sample bank exists independently of execution.
4. The mechanism-pair work unit runs all tasks serially and releases memory afterward.
5. Atomic sharding and resume survive forced interruption tests.
6. Actual M4 Pro hardware, memory, process, and thread settings are captured.
7. Serial calibration reports peak memory and time per mechanism pair.
8. Any accepted multi-worker profile is proven scientifically equivalent to serial mode.
9. Resolution and tasks-per-mechanism decisions are recorded from calibration.
10. The 50-mechanism variance pilot completes and produces hierarchical estimates.
11. Production batches execute until the accepted stopping rule or hard cap.
12. A high-resolution confirmation subset is completed.
13. One immutable report package separates scientific effects from runtime observations.
14. The final sample bank is frozen for a later paired A* campaign.
15. All tests, lint, formatting, and type checks pass.

## Cursor starter prompt

```text
Implement Sprint V2.10 (issue `production_monte_carlo_orchestration_v2_9`) after the
V2.8 / V2.9 shared-Q evidence is reviewed. Build a
production Monte Carlo orchestration layer for one solver: Dijkstra. Do not run A*,
bidirectional search, PRM, RRT, or any solver list. Separate mechanism/task sample-bank
construction from expensive search execution. Make one mechanism pair the atomic work
unit; reuse its shared Q topology, run all tasks serially, write an atomic shard, and
release memory. Add resumable manifests, deterministic merge tooling, hierarchical
mechanism-aware analysis, sequential precision reports, resolution and task-count
calibration, and a high-resolution confirmation subset. Default to workers=1 and one
numerical thread on the user's M4 Pro Mac. Capture the actual macOS hardware and memory
configuration, benchmark peak memory and throughput, and allow optional 1/2/4-worker
calibration only after scientific equivalence is proven. Keep visualization out of the
production search loop. Freeze the completed mechanism/task bank for a later A* sprint.
```
