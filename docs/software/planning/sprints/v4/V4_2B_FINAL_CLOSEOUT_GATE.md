# Sprint V4.2B — Final Canonical Evidence and Closeout Gate

- **Status:** active continuation of Sprint V4.2B; no new sprint number
- **Prepared against:** `main` at `e98ca1f5c7dcf4e21f40185d36c8ba1a6664bf7b`
- **Authorization:** existing V4-220–V4-229 authorization remains in force
- **Depends on:** merged PR #27 implementation checkpoint; frozen V3.6D registry; closed V4.0/V4.1; historical V4.2/V4.2A
- **Blocks:** V4.3 intrinsic gravity-free static wrench and all later span-family effect columns
- **Fresh artifact root:** `results/v4_review/v4_2b_span_controlled_corrective_closeout/`
- **Normative decisions:** ADR-027, ADR-028, ADR-029, and ADR-030
- **Closeout rule:** V4-229 returns `ACTIVE_SPRINT.md` to no authorization; V4.3 is not activated in the same change

## 1. Program decision

Do **not** create Sprint V4.2C.

PR #27 is an implementation checkpoint inside the already-active V4.2B corrective sprint. It landed the mounted-output adapter, mounted span realization, corrected atlas generator, common candidate-Q graph, finite-edge adapter, common-physical task bank, compressed-row inventory, and clean-source guard. It explicitly did **not** generate canonical V4.2B evidence, complete the corrected visual audit, write the final closeout, or reset authorization.

Creating another sprint would obscure that V4.2B has not yet satisfied its own exit criteria. This document is therefore the final closeout gate for the existing V4-220–V4-229 range.

## 2. Closeout question

> Can the mounted-coordinate span family now produce one complete, reproducible, pair-fair geometry and planning package in which the final search topology is shared, numerical failures remain fail-closed, all retained rows are auditable, and the result is generated from a clean implementation revision?

This is a software and evidence gate. It is not a new mechanism study and does not add a new scientific estimand.

## 3. Current checkpoint

### Landed and retained

The merged implementation already provides:

- a serializable mounted-output mechanism adapter;
- `realize_mounted_span_case(...)` as the new V4.2B consumer path;
- zero-centered mounted robot-joint coordinates with unchanged `J_g`;
- a fresh V4.2B geometry-atlas generator and config;
- per-case compressed `geometry_samples.jsonl.gz` files;
- one common candidate-Q lattice and shared valid-node mask;
- a finite-edge compilation adapter;
- a frozen ten-task common-physical bank;
- canonical-output dirty-tree refusal;
- retained-package guards and baseline digests.

### Not yet closed

The following remain open:

1. strict separation of `+inf`, `NaN`, `-inf`, and finite negative edge costs;
2. one **final planner-facing edge set** after connector evaluation, not merely one candidate adjacency;
3. the complete mounted-output adapter proof suite;
4. mandatory manifest/provenance fields and full row-schema validation;
5. the corrected V4.2B visual planning audit;
6. a clean canonical V4.2B result package;
7. full repository quality gates and recorded test counts;
8. canonical roadmap/README normalization;
9. an independent package review, closeout note, and authorization reset.

## 4. Scientific and software invariants

V4.2B closes only if every downstream record obeys the same physical chain:

\[
\mathcal U
\xrightarrow{g}
\mathcal Q_{\mathrm{mounted}}
\xrightarrow{f}
\mathcal X.
\]

For every supported axis:

\[
q_{\mathrm{mounted}}
=
q_{\mathrm{native}}-q_{\mathrm{offset}},
\qquad
\frac{dq_{\mathrm{mounted}}}{du}
=
\frac{dq_{\mathrm{native}}}{du}.
\]

The mounted coordinate is authoritative for:

- `PhysicalState.q`;
- FK and `J_f`;
- `geometry_snapshot`;
- Q sampling and task definitions;
- planner paths and goal predicates;
- V4.3 static-wrench evaluation.

The native follower angle remains provenance only.

## 5. Final closeout phases

The existing work-package IDs remain authoritative. This gate tightens the unfinished portions of V4-221, V4-224, V4-225, V4-227, V4-228, and V4-229.

### Gate A — correctness hardening

1. Complete mounted-output adapter tests.
2. Make edge-value classification strict.
3. Compile one common admitted edge set for the pair.
4. Run the all-case topology and mounted-coordinate tests.

### Gate B — evidence hardening

1. Make the artifact verifier require every provenance field.
2. Parse complete geometry rows through the real schema.
3. Generate the corrected common-physical visual audit.
4. Ensure the root manifest recursively covers both geometry and planning subpackages.

### Gate C — canonical generation and closeout

1. Commit the final implementation with no V4.2B evidence present.
2. Run all quality gates from a clean tree.
3. Generate the canonical package from that exact commit.
4. Verify and independently review the package.
5. Commit evidence and closeout notes.
6. Update project documentation and reset authorization.

## 6. V4-221 completion — mounted-output proof contract

### Required implementation state

The adapter remains the single owner of the coordinate transformation. Do not scatter `q - offset` arithmetic through the atlas, planner, FK, or visualization layers.

The adapter must preserve:

- input bounds;
- branch and assembly state;
- periodicity;
- link geometry;
- analytic `J_g`;
- certificate thresholds.

It must transform:

- forward output;
- inverse target coordinate;
- certificate output bounds;
- output-space bounds;
- inverse lookup/table Q values;
- serialized provenance.

### Required tests

Add or complete a focused test module, preferably:

```text
tests/mechanisms/test_output_mounting.py
```

It must cover:

1. scalar nonzero offset;
2. two-axis offsets;
3. zero-offset identity behavior;
4. forward/inverse round trip over interior and endpoint samples;
5. finite-difference agreement with the unchanged analytic Jacobian;
6. `OperatingBranch` serialization/deserialization round trip;
7. preservation of branch selector and certificate metadata;
8. explicit refusal or detection of double mounting;
9. all five span records and all 17 realized cases;
10. unchanged `boundary_stress_only` classification for 175°.

### Exit assertion

```python
assert mounted_bounds == approx(registry_usable_bounds)
assert midpoint(mounted_bounds) == approx(0.0)
assert mounted.jacobian(u) == approx(native.jacobian(u))
assert restored.forward(u) == approx(mounted.forward(u))
assert mounting_application_count == 1
```

## 7. V4-224 completion — one final paired search topology

### Problem to resolve

The current implementation freezes one common candidate-Q topology, but connector-level finite-edge compilation can still be performed independently per mechanism. That can produce different final search adjacency even when the candidate graph is shared.

### Required architecture

Add a paired edge-admission compiler. A suitable result family is:

```python
@dataclass(frozen=True)
class PairedCompiledSearchGraph:
    graph: SearchGraph
    edge_costs: Mapping[str, EdgeCost]
    rejected_candidates: Mapping[tuple[int, int], Mapping[str, EdgeAdmission]]
    admitted_edge_ids: tuple[tuple[int, int], ...]
```

The exact class name may follow repository style. The semantics are fixed:

1. begin with one `PairedQPlanningGraph` candidate adjacency;
2. evaluate the declared continuous Q local motion through every paired arm;
3. classify each arm's edge result under ADR-030;
4. admit the edge to the primary graph only when every paired arm reports a finite nonnegative cost;
5. if either arm reports unavailable local motion, omit that edge for both arms and retain per-arm diagnostics;
6. assign mechanism-specific actuator costs to the one shared admitted edge ID;
7. never construct two final graphs and intersect them after planner execution.

A mechanism-specific connector disagreement is diagnostic data, not permission to change the primary pair topology.

### Required tests

For all 17 cases at smoke and production lattice shapes:

```python
assert fourbar_node_ids == gearbox_node_ids
assert fourbar_candidate_edge_ids == gearbox_candidate_edge_ids
assert fourbar_admitted_edge_ids == gearbox_admitted_edge_ids
assert q_fourbar == approx(q_gearbox)
assert x_fourbar == approx(x_gearbox)
```

Also test:

- an edge available in both arms;
- an edge unavailable in both arms;
- an edge available in only one arm;
- a case that becomes disconnected after common admission;
- deterministic rejected-edge provenance;
- Dijkstra/A* parity over the resulting common graph.

### Exit assertion

The graph object passed to Dijkstra/A* is physically the same topology for both mechanisms. Only the cached actuator edge costs differ.

## 8. V4-225 completion — strict nonfinite edge semantics

### Normative classification

At the adapter boundary:

| Edge evaluation | Meaning | Required behavior |
| --- | --- | --- |
| finite and `>= 0` | available local motion | admit and cache |
| `+inf` | declared unavailable local motion | omit before search; retain diagnostic |
| `NaN` | numerical/programming failure | raise typed error |
| `-inf` | invalid negative-infinite cost | raise typed error |
| finite `< 0` | invalid negative cost | raise typed error |

Generic Dijkstra/A* remains strict and receives only finite nonnegative edges.

### Bounded implementation change

The current `compile_finite_neighbors(...)` may remain for single-arm uses, but it must distinguish the categories above. The paired primary experiment must use the paired compiler from V4-224.

A longer-term typed edge-evaluation object may replace the `+inf` sentinel, but that refactor is not required for V4.2B closeout.

### Required tests

```text
+inf is omitted as unavailable_local_motion
NaN raises
-inf raises
finite negative raises
finite zero is admitted
finite positive is admitted
all unavailable returns found=False rather than planner_exception
Dijkstra and A* agree on cost and feasibility
```

No V4.2B planner record may contain a nonfinite-cost exception.

## 9. V4-226 completion — corrected visual planning audit

### Task contract

Consume the already-frozen `common_physical_span_bank_v1`. Do not regenerate or replace tasks after planner outcomes exist.

For each task, all 17 cases receive the same:

- exact mounted `start_q`;
- Cartesian start;
- goal center and radius;
- represented goal candidate IDs and ordering;
- Q local-motion model;
- common paired lattice topology.

The mechanisms retain different `start_u`, goal preimages, U embeddings, and actuator costs.

### Planner scope

Retain the V3.6B/V4.2A diagnostic families where currently implemented:

- input-linear direct;
- output-linear direct;
- lattice Dijkstra;
- lattice A*;
- native PRM;
- native RRTConnect;
- optional OMPL PRM;
- optional OMPL RRTConnect.

The primary topology assertion applies to the paired lattice family. Direct, roadmap, and tree planners remain family controls under the same physical task.

### Artifact layout

```text
planning_audit/
├── summary.json
├── failures.json
├── index.html
├── cases/<case_id>/index.html
├── cases/<case_id>/tasks/<task_id>.html
└── data/*.jsonl.gz
```

Static panels are authoritative. Animations remain skipped unless explicitly approved because they add repository weight without changing the closeout estimand.

### Required report fields

- task and case IDs;
- mechanism and planner IDs;
- shared start/goal provenance;
- candidate and admitted graph counts;
- rejected-edge reasons by mechanism;
- feasibility and typed failure reason;
- selected goal ID;
- U/Q/X path lengths;
- lattice expansions/generated/stale counts;
- roadmap/tree family metrics;
- common final edge-set digest;
- config, task-bank, registry, and code digests;
- no-inference statement.

### Closeout requirements

- all 170 case-task cells are present;
- all expected planner rows or typed unavailable/failure rows are present;
- zero silent row drops;
- zero nonfinite-cost planner exceptions;
- OMPL absence is typed, not omitted;
- no task is replaced after inspection.

## 10. V4-227 completion — fail-closed retained artifact

### Mandatory root manifest fields

The verifier must require, not merely accept when present:

```text
schema_version
package
manifest_inventory_rule
source_git_revision
source_git_dirty
config_digest
v3_6d_registry_digest
common_task_bank_digest
case_ids
n_rows
n_typed_failures
n_silent_drops
files
files_digest
```

Additional subpackage counts are required for the final package:

```text
geometry_case_count
geometry_row_count
planning_case_task_count
planning_row_count
```

### Required checks

- `package` exactly equals the V4.2B package ID;
- `schema_version` exactly equals the current package schema;
- `source_git_dirty is False`;
- `source_git_revision` is a 40-character hexadecimal commit SHA;
- `case_ids` contains the exact 17 unique case IDs;
- `n_silent_drops == 0`;
- `files_digest` is nonempty and matches exactly;
- every required file exists, is tracked, and matches SHA-256 and byte count;
- every compressed file decompresses;
- every JSONL row parses through the actual strict `AtlasRow` or planner-row schema;
- `cases.json`, `resolved_config.json`, `rank_fields.json`, summaries, and submanifests pass strict schema validation;
- unexpected listed files and unlisted required files both fail;
- omission of any mandatory manifest key fails.

### Manifest structure

Use either:

1. one root manifest recursively inventorying every retained file; or
2. root + subpackage manifests, where the root inventories and hashes the geometry and planning manifests and the verifier recursively validates both.

Do not leave the visual audit outside the canonical package inventory.

### Storage discipline

The generator must record total package bytes and reject any individual tracked file at or above the GitHub 100 MiB limit. Prefer compressed machine-readable data, shared static assets, and no duplicated embedded binary payloads.

A broader repository evidence-storage ADR remains separate from this closeout.

## 11. V4-228 completion — quality, CI, and documentation normalization

### Required local quality gate

From a clean implementation commit:

```bash
git status --porcelain --untracked-files=all  # must be empty
PYTHONPATH=src MPLBACKEND=Agg python -m pytest
xargs ruff check < tests/v4/data/v4_2b_lint_paths.txt
xargs ruff format --check < tests/v4/data/v4_2b_lint_paths.txt
```

Full pytest must pass. Every Python file on the V4.2B lint path list must be
Ruff-clean, format-clean, and (for `src/` modules) mypy-clean under
`--follow-imports=silent`. Those scoped checks are also asserted by
`tests/v4/test_v4_2b_lint_baseline.py`.

Full-tree `ruff check .`, `ruff format --check .`, and `mypy src` are frozen
historical debt. Counts must not grow relative to
`tests/v4/data/frozen_full_tree_lint_baseline.json`. They are not a
zero-error whole-repository gate, and V4.2B does not authorize a
repo-wide lint campaign.

Record:

- Python version;
- package versions/environment lock;
- passed, skipped, xfailed, and failed counts;
- OMPL availability;
- runtime;
- source revision.

### Focused closeout tests

At minimum:

```text
tests/mechanisms/test_output_mounting.py
tests/v4/test_v4_2b_mounted_span_realization.py
tests/v4/test_v4_2b_shared_topology.py
tests/v4/test_v4_2b_paired_edge_admission.py
tests/v4/test_v4_2b_finite_edge_contract.py
tests/v4/test_v4_2b_common_physical_bank.py
tests/v4/test_v4_2b_corrective_export.py
tests/v4/test_v4_2b_artifact_integrity.py
tests/v4/test_v4_2b_clean_source.py
tests/v4/test_v4_2b_closeout.py
tests/v4/test_v4_2b_lint_baseline.py
```

### CI

Add a minimal GitHub Actions workflow unless repository policy explicitly rejects it:

- Python 3.11 and 3.12;
- editable dev install;
- Ruff check and format check on the V4.2B path list;
- mypy on V4.2B `src/` modules (`--follow-imports=silent`);
- full pytest, including the frozen full-tree lint-count baseline;
- no canonical artifact generation in CI.

### Documentation normalization

Before closeout, update:

- root `README.md` to describe the V3/V4 architecture and current status;
- `docs/software/V4_PROJECT_PLAN.md` to include V4.2A/V4.2B and make V4.3 consume V4.2B;
- `docs/software/VERSION_MATRIX.md`;
- V4 sprint index;
- ADR index;
- planning index;
- V4.3 sprint dependency and snapshot-source text;
- project-index canvas links, if maintained.

The V4.0 state-tolerance propagation and target-metric SPD checks remain documented technical debt, not V4.2B blockers.

## 12. V4-229 — canonical generation, review, and closeout

### Commit sequence

#### Commit I — implementation

Contains:

- source corrections;
- tests;
- strict schemas;
- audit generator;
- CI and documentation updates;
- no generated V4.2B evidence.

Record this commit as `source_git_revision`.

#### Clean generation

```bash
git status --porcelain --untracked-files=all  # must be empty
PYTHONPATH=src MPLBACKEND=Agg python -m pytest
python scripts/generate_v4_2b_span_controlled_corrective.py
python scripts/verify_v4_2b_artifact.py \
  results/v4_review/v4_2b_span_controlled_corrective_closeout/
```

Scoped V4.2B Ruff/format/mypy and the frozen full-tree count ceiling run
inside pytest via `tests/v4/test_v4_2b_lint_baseline.py`. Do not treat
whole-tree Ruff/mypy as a zero-error gate.

The generator must refuse a dirty tree and a nonempty canonical output root before writing.

#### Independent review

Review the generated package before committing evidence.

Coordinate checks:

- all five mounted intervals centered at zero;
- exact frozen usable widths;
- native-plus-offset reconstruction;
- unchanged `J_g`;
- 175° remains boundary stress.

Geometry checks:

- 17 cases;
- `17 × 33 × 33 × 3 = 55,539` geometry rows or typed failures;
- zero silent drops;
- exact shared Q/X within each case;
- rank attribution preserved.

Planning checks:

- ten frozen common tasks;
- 170 case-task cells;
- common final lattice edge IDs within every pair;
- zero nonfinite-cost planner exceptions;
- rejected-edge diagnostics visible;
- no outcome-driven task replacement.

Artifact checks:

- strict manifest keys;
- recursive file hashes;
- successful decompression and full-schema parsing;
- clean source revision;
- historical package digests unchanged;
- package byte totals recorded.

#### Commit E — evidence and closeout

Contains:

- canonical V4.2B package;
- independent review note;
- closeout note;
- updated status documents;
- no V4.3 implementation.

#### Authorization reset

Set `ACTIVE_SPRINT.md` to:

```text
Current focus: none. Sprint V4.2B is completed. Sprint V4.3 remains drafted / blocked.
Code authorization: none.
```

Do not activate V4.3 in the same commit.

## 13. Canonical artifact contract

```text
results/v4_review/v4_2b_span_controlled_corrective_closeout/
├── geometry_atlas/
│   ├── manifest.json
│   ├── summary.json
│   ├── cases/<17 case ids>/geometry_samples.jsonl.gz
│   └── index.html
├── planning_audit/
│   ├── manifest.json
│   ├── summary.json
│   ├── failures.json
│   ├── cases/<case id>/...
│   └── index.html
├── methods/
│   ├── mounted_coordinates.md
│   ├── paired_topology.md
│   ├── finite_edge_semantics.md
│   └── provenance.md
├── manifest.json
├── resolved_config.json
├── cases.json
├── rank_fields.json
├── summary.json
├── README.md
└── index.html
```

Historical V4.2/V4.2A packages remain immutable and linked as superseded diagnostic evidence.

## 14. Sprint exit criteria

V4.2B is complete only when all are true:

1. mounted-output adapter proof suite passes, including serialization and double-mount protection;
2. every supported span realizes exact zero-centered mounted bounds;
3. V3.6D registry and certificate digests are unchanged;
4. `+inf` alone represents unavailable local motion at the adapter boundary;
5. `NaN`, `-inf`, and negative finite costs fail closed;
6. one final admitted lattice edge set is shared across each mechanism pair;
7. the complete geometry atlas contains 55,539 rows or typed failures with zero silent drops;
8. the ten-task common-physical audit is generated across all 17 cases;
9. no nonfinite-cost planner exception remains;
10. all mandatory manifest fields are present and recursively verified;
11. every retained row parses through the actual schema;
12. full pytest passes, V4.2B-touched Python is Ruff/format/mypy clean, and frozen full-tree lint counts do not grow;
13. historical V3 and V4.0–V4.2A package digests are unchanged;
14. canonical evidence was generated from a clean implementation commit;
15. root README, V4 plan, sprint index, version matrix, and V4.3 dependency are current;
16. independent review accepts the package;
17. `ACTIVE_SPRINT.md` returns to no authorization;
18. V4.3 remains separately blocked.

## 15. Stop conditions

Stop and request review rather than improvising if:

- the mount changes `J_g`;
- the registry digest or certificate profile changes;
- common final topology cannot be obtained without changing the declared Q local-motion model;
- the common task bank must be replaced after planner outcomes exist;
- strict schema parsing exposes silent historical row loss;
- a canonical output would require overwriting V4.2/V4.2A;
- the package cannot fit the declared storage contract;
- V4.3 code appears necessary to close V4.2B;
- full regression failures cannot be attributed and resolved inside the authorized range.

## 16. Compact Cursor prompt

> Continue the already-active Sprint V4.2B on `main` after PR #27. Do not create V4.2C and do not activate V4.3. Implement only the remaining V4-220–V4-229 closeout work. Complete mounted-output serialization/finite-difference/double-mount tests; make `+inf` the only unavailable-edge sentinel while NaN, `-inf`, and negative costs fail closed; compile one final paired edge set before Dijkstra/A* so four-bar and gearbox receive identical planner topology; harden the V4.2B verifier so all manifest/provenance fields are mandatory and every row is parsed through the real schema; generate the common-physical visual audit; run full pytest/Ruff/format/mypy gates; generate the complete V4.2B package from a clean implementation commit; independently review it; update README/V4 roadmap/V4.3 dependencies; commit evidence; and return `ACTIVE_SPRINT.md` to no authorization. Preserve all V3 and V4.0–V4.2A evidence byte-for-byte.
