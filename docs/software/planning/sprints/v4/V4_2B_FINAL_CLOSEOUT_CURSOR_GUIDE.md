# Cursor Guide — V4.2B Final Closeout Gate

**Repository:** `mfbailey91/Function_Generators_in_Open_Chains`
**Baseline:** `main` at `e98ca1f5c7dcf4e21f40185d36c8ba1a6664bf7b`
**Authorization:** V4-220–V4-229 only
**Do not create:** V4.2C
**Do not implement:** V4.3 or later work

## 1. Read in this order

1. `docs/software/planning/ACTIVE_SPRINT.md`
2. `docs/software/planning/sprints/v4/SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md`
3. `docs/software/planning/sprints/v4/V4_2B_FINAL_CLOSEOUT_GATE.md`
4. `docs/software/architecture/adr/ADR-029-mounted-output-coordinate.md`
5. `docs/software/architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md`
6. `src/inequality_mechanisms/mechanisms/output_mounting.py`
7. `src/inequality_mechanisms/experiments/span_cases.py`
8. `src/inequality_mechanisms/graphs/paired_q_planning.py`
9. `src/inequality_mechanisms/adapters/finite_search_edges.py`
10. `src/inequality_mechanisms/experiments/v4/span_controlled_corrective.py`
11. `src/inequality_mechanisms/audits/v4_2b_artifact.py`
12. current V4.2B tests and frozen configs

Stop if `main` has moved and the changed code overlaps the files above. Rebase the plan deliberately rather than applying it blindly.

## 2. Establish the checkpoint

```bash
git status --short
git rev-parse HEAD
python -m pytest \
  tests/v4/test_v4_2b_clean_source.py \
  tests/v4/test_v4_2b_artifact_integrity.py \
  tests/v4/test_v4_2b_common_physical_bank.py \
  tests/v4/test_v4_2b_finite_edge_contract.py \
  tests/v4/test_v4_2b_shared_topology.py \
  tests/v4/test_v4_2b_mounted_span_realization.py \
  tests/v4/test_v4_2b_phase0_freeze.py -q
```

Record the baseline result in the closeout working note. Confirm the canonical V4.2B result root does not yet exist.

## 3. Commit 1 — strict edge semantics

### Change

Update `src/inequality_mechanisms/adapters/finite_search_edges.py` so classification is explicit:

```python
if math.isnan(weight):
    raise ValueError(...)
if weight == -math.inf:
    raise ValueError(...)
if weight == math.inf:
    reject_as_unavailable(...)
    continue
if weight < 0.0:
    raise ValueError(...)
admit(weight)
```

Do not use `not math.isfinite(weight)` as the unavailable-motion test.

### Tests

Extend `tests/v4/test_v4_2b_finite_edge_contract.py` with:

```text
+inf -> omitted
NaN -> raises
-inf -> raises
finite negative -> raises
zero -> admitted
positive finite -> admitted
```

Keep generic search unchanged and strict.

### Commit message

```text
Tighten V4.2B nonfinite edge semantics
```

## 4. Commit 2 — paired final edge admission

### Add

A paired compiler, preferably beside `paired_q_planning.py` or in a focused module such as:

```text
src/inequality_mechanisms/graphs/paired_edge_admission.py
```

### Required API shape

```python
@dataclass(frozen=True)
class PairedCompiledSearchGraph:
    graph: SearchGraph
    edge_costs: Mapping[str, EdgeCost]
    admitted_edge_ids: tuple[tuple[int, int], ...]
    rejected_candidates: Mapping[
        tuple[int, int], Mapping[str, EdgeAdmission]
    ]
```

### Algorithm

For every directed candidate edge from `PairedQPlanningGraph.topology`:

1. evaluate every arm's connector/cost;
2. apply ADR-030 classification;
3. if any arm returns `+inf`, exclude for all arms and store each arm's result;
4. if any arm returns NaN, `-inf`, or negative finite, raise;
5. if every arm is finite and nonnegative, admit one common edge ID;
6. cache one cost per arm under that edge ID.

The returned `graph.neighbors(...)` is common. The mechanism-specific difference lives only in `edge_costs[name]`.

### Tests

Add:

```text
tests/v4/test_v4_2b_paired_edge_admission.py
```

Cover:

- both available;
- both unavailable;
- one available / one unavailable;
- invalid numeric value in either arm;
- disconnected result;
- deterministic edge ordering and digest;
- Dijkstra/A* parity.

Then extend all-case topology tests to compare the final admitted edge IDs, not only candidate adjacency.

### Commit message

```text
Compile one final paired V4.2B search topology
```

## 5. Commit 3 — complete mounted-output tests

### Add or complete

```text
tests/mechanisms/test_output_mounting.py
```

Use a minimal affine branch fixture plus one real four-bar span record.

Required tests:

```text
scalar offset
vector offset
zero offset
forward/inverse endpoints and interior
finite-difference Jacobian
unchanged analytic Jacobian
serialization round trip
selector/provenance preservation
double-mount detection
all five spans / 17 cases
```

Do not change the V3.6D registry or `PRIMARY_CERTIFICATE`.

### Commit message

```text
Complete the mounted-output proof contract
```

## 6. Commit 4 — harden the artifact verifier

### Update

```text
src/inequality_mechanisms/audits/v4_2b_artifact.py
```

Add `REQUIRED_MANIFEST_KEYS`. Missing keys must fail before file iteration.

Require:

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

Require exact 17 case IDs and `n_silent_drops == 0`.

Replace the three-key JSONL check with strict row deserialization. Reuse the real row type or add one schema validator in the experiment package; do not maintain a second approximate schema in the verifier.

Add root/subpackage recursive verification for the later planning audit.

### Tests

For every mandatory key, create a deletion test. Also test:

- wrong package;
- wrong schema version;
- dirty source flag;
- malformed SHA;
- missing files digest;
- wrong case set;
- malformed full row with the three old keys still present;
- unexpected file;
- omitted required file;
- gzip truncation;
- hash, byte, and row mismatch.

### Commit message

```text
Make V4.2B retained evidence fully fail closed
```

## 7. Commit 5 — corrected planning-audit generator

### Reuse

Reuse V4.2A rendering and planner adapters, but consume:

- `realize_mounted_span_case(...)`;
- `common_physical_span_bank_v1`;
- the paired final-edge compiler;
- fresh V4.2B paths and schemas.

Do not call V4.2A's per-case task reauthoring path.

### Suggested files

```text
configs/v4/planar2r_span_controlled_corrective_audit_v1.json
src/inequality_mechanisms/experiments/v4/span_controlled_corrective_audit.py
src/inequality_mechanisms/visualization/v4/span_controlled_corrective_audit.py
scripts/generate_v4_2b_span_controlled_corrective.py
```

The existing V4.2B generator may become an orchestrator that writes both `geometry_atlas/` and `planning_audit/`.

### Assertions before writing

```python
assert task_bank_digest == frozen_digest
assert final_edge_ids_fourbar == final_edge_ids_gearbox
assert start_q_fourbar == approx(start_q_gearbox)
assert start_x_fourbar == approx(start_x_gearbox)
assert goal_definition_fourbar == goal_definition_gearbox
```

### Artifact behavior

- static HTML and PNGs are authoritative;
- skip animations;
- retain all failures;
- retain optional-backend unavailability;
- no mechanism ranking;
- no task replacement.

### Commit message

```text
Add the V4.2B common-physical planning audit
```

## 8. Commit 6 — closeout tests, CI, and docs

### Add

```text
tests/v4/test_v4_2b_closeout.py
.github/workflows/ci.yml
```

The closeout test should enforce:

- exact case set;
- expected geometry-row total;
- zero silent drops;
- one final topology digest per case shared by the pair;
- exact task-bank digest;
- required manifest fields;
- clean source revision format;
- historical package digests unchanged;
- V4.3 still blocked.

### Update docs

- root `README.md`;
- `docs/software/V4_PROJECT_PLAN.md`;
- `docs/software/VERSION_MATRIX.md`;
- V4 sprint index;
- V4.3 dependency text;
- active-sprint file only at final reset.

### Commit message

```text
Prepare V4.2B for canonical generation
```

## 9. Clean quality gate

With no generated V4.2B evidence in the tree:

```bash
git status --porcelain --untracked-files=all
PYTHONPATH=src MPLBACKEND=Agg python -m pytest
xargs ruff check < tests/v4/data/v4_2b_lint_paths.txt
xargs ruff format --check < tests/v4/data/v4_2b_lint_paths.txt
```

Full pytest must pass. V4.2B-touched Python must be Ruff, format, and
mypy clean. Full-tree Ruff/mypy are frozen debt in
`tests/v4/data/frozen_full_tree_lint_baseline.json` and must not grow;
they are not a passing whole-repository gate.

Do not proceed with canonical generation if pytest fails, if a V4.2B
file is unclean, if baseline counts regress, or if porcelain is dirty.

Record the exact implementation SHA:

```bash
git rev-parse HEAD
```

## 10. Canonical generation

Ensure the output root is absent or empty, then:

```bash
python scripts/generate_v4_2b_span_controlled_corrective.py
python scripts/verify_v4_2b_artifact.py \
  results/v4_review/v4_2b_span_controlled_corrective_closeout/
```

The manifest must record the implementation SHA, not the later evidence commit.

## 11. Independent review checklist

### Geometry

```text
17 cases
55,539 geometry rows or typed failures
0 silent drops
mounted Q centered at zero
shared Q/X within case
identity J_g = I
175° boundary-stress label retained
```

### Planning

```text
10 common tasks
170 case-task cells
identical final lattice edge IDs within pair
0 nonfinite-cost planner exceptions
all expected rows or typed failures
OMPL unavailability retained
```

### Artifact

```text
strict root and submanifest verification
all files tracked
all hashes and sizes match
all JSONL rows strict-parse
source_git_dirty = false
source_git_revision = implementation commit
historical digests unchanged
```

## 12. Evidence and closeout commit

Commit:

- generated package;
- review note;
- closeout note;
- final project documentation;
- `ACTIVE_SPRINT.md` reset to none.

Do not include V4.3 source or activation.

Suggested commit message:

```text
Close V4.2B with canonical mounted span evidence
```

## 13. Final stop

After the closeout commit, verify:

```bash
git status --short
```

and confirm `ACTIVE_SPRINT.md` says no authorization. V4.3 requires a new reviewed activation.
