# Cursor Implementation Guide — Sprint V4.2B

**Authorized work when activated:** V4-220–V4-229 only

**Branch reviewed for planning:** `Version_4_Kinematic_Transmission_Geometry` at `db398268bf2de7efc8ca7ab33e49d787c8b4cef4`

**Canonical sprint contract:** `SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md`

## 1. Read before editing

Read these files in order:

1. `docs/software/planning/ACTIVE_SPRINT.md`;
2. `docs/software/architecture/adr/ADR-029-mounted-output-coordinate.md`;
3. `docs/software/planning/sprints/v4/SPRINT_V4_2B_SPAN_CONTROLLED_ATLAS_CORRECTIVE_CLOSEOUT.md`;
4. `src/inequality_mechanisms/mechanisms/span_synthesis.py`;
5. `src/inequality_mechanisms/mechanisms/span_registry.py`;
6. `src/inequality_mechanisms/experiments/span_cases.py`;
7. V4.2/V4.2A generators and tests;
8. `src/inequality_mechanisms/audits/v4_artifact_guard.py`;
9. `src/inequality_mechanisms/adapters/lattice_edge_cost.py` and `search/core.py`.

Stop immediately if the branch head or frozen V3.6D digest differs from the reviewed lineage without an explicit reviewed update.

## 2. Commit and authorization sequence

Use this order:

```text
A. planning commit — docs only, ACTIVE_SPRINT remains none
B. activation commit — authorize V4-220–V4-229 only
C. mounted-coordinate implementation + red/green tests
D. paired-topology and finite-edge implementation + tests
E. V4.2B configs/generators/exporters + tests
F. clean implementation commit
G. generate evidence from clean implementation HEAD
H. evidence + closeout commit
I. authorization-reset commit, or include reset in reviewed closeout
```

Never combine V4.3 activation with V4.2B closeout.

## 3. Phase 0 — establish baseline and freeze checks

Before code changes:

```bash
git status --short
git rev-parse HEAD
python -m pytest tests/v4 -q
```

Record:

- current HEAD;
- V3.6D registry digest;
- git-tracked package digests for V4.0, V4.1, V4.2, and V4.2A;
- current test count and failures;
- OMPL availability only as environment provenance.

Do not regenerate any retained package during baseline capture.

## 4. Phase 1 — write failing scientific-invariant tests first

Add focused tests before implementation.

Suggested files:

```text
tests/mechanisms/test_output_mounting.py
tests/v4/test_v4_2b_mounted_span_realization.py
tests/v4/test_v4_2b_shared_topology.py
tests/v4/test_v4_2b_finite_edge_contract.py
tests/v4/test_v4_2b_artifact_integrity.py
tests/v4/test_v4_2b_corrective_export.py
```

The first red tests should prove the current defect:

```python
assert native_midpoint != 0.0
assert registry.range_definition midpoint == 0.0
assert current_realized_branch midpoint != registry midpoint
```

Then state the corrected invariant:

```python
assert mounted_branch.certificate.output_lower == approx(range_lower)
assert mounted_branch.certificate.output_upper == approx(range_upper)
assert midpoint(mounted_bounds) == approx(0.0)
```

Do not encode current wrong native ranges as approved expectations.

## 5. Phase 2 — implement the mounting adapter

Create a reusable adapter rather than span-specific arithmetic scattered through generators.

Preferred boundary:

```text
src/inequality_mechanisms/mechanisms/output_mounting.py
```

The adapter may be implemented as:

- a serializable mechanism wrapper plus a helper that rebuilds an ordinary `OperatingBranch`; or
- a serializable operating-branch wrapper if current branch internals make that safer.

Regardless of class shape, the public behavior is fixed:

```python
def forward(u):
    return native.forward(u) - offset

def inverse(q_joint):
    return native.inverse(q_joint + offset)

def jacobian(u):
    return native.jacobian(u)
```

The mounted branch must shift:

- output lower/upper bounds;
- output-space bounds;
- inverse lookup/table Q values;
- serialized Q samples and diagnostics.

It must not shift:

- U bounds;
- assembly state;
- link lengths;
- branch sign;
- `J_g`;
- certificate thresholds.

Add an explicit provenance flag such as:

```text
output_coordinate_kind: mounted_joint
native_output_offset_rad: [...]
mounting_application_count: 1
```

The exact field names may follow existing schema style, but double application must be test-detectable.

## 6. Phase 3 — correct span realization at one owner

Keep one owner for frozen-registry realization. Do not patch V4.2 and V4.2A generators independently.

Recommended flow in `experiments/span_cases.py`:

```text
registry record
  -> native bar / native operating branch
  -> mounted branch using q_offset_rad
  -> registry-range invariant check
  -> span-matched affine gearbox from mounted branch
  -> RealizedSpanCase with native + mounted provenance
```

Add a helper with a name that exposes the decision, for example:

```python
realize_mounted_span_case(...)
```

Keep the old historical function only when frozen readers require it. New V4.2B code must call the mounted owner explicitly. Do not silently change a function used to reproduce V4.2/V4.2A unless compatibility is proven and historical package regeneration remains blocked.

## 7. Phase 4 — rebuild the geometry atlas under a fresh schema

Do not overwrite the V4.2 generator or package. Add V4.2B modules, config, and script, for example:

```text
configs/v4/planar2r_span_controlled_corrective_v1.json
src/inequality_mechanisms/experiments/v4/span_controlled_corrective.py
src/inequality_mechanisms/experiments/v4/span_controlled_corrective_config.py
src/inequality_mechanisms/visualization/v4/span_controlled_corrective.py
scripts/generate_v4_2b_span_controlled_corrective.py
```

Use V4.0 `geometry_snapshot`; do not copy its mathematics.

Within one case, assert before export:

```python
q_fourbar == q_gearbox == q_identity
x_fourbar == x_gearbox == x_identity
```

Across cases, Q domains differ by span but share zero-centered physical joint semantics. Compare cases through stable normalized eta/sample identities, not by pretending all spans have identical Q bounds.

## 8. Phase 5 — build one paired graph, not two graphs compared afterward

Introduce one common-Q graph builder whose output owns:

- Q sample IDs;
- common node-validity mask;
- candidate adjacency;
- final common edge IDs;
- per-mechanism U embeddings and finite edge costs.

Do not use `_shared_weight_note` as the primary fairness mechanism. It may remain only as a compatibility diagnostic for historical packages.

The builder should fail before planner execution when paired topology differs. A useful result shape is:

```python
@dataclass(frozen=True)
class PairedQPlanningGraph:
    topology: ...
    q_by_node: ...
    x_by_node: ...
    arms: Mapping[str, EmbeddedPlanningGraph]
    rejected_candidates: Mapping[str, ...]
```

Exact type names may follow the existing graph architecture.

## 9. Phase 6 — filter unavailable local motions before search

Do not weaken generic search into accepting arbitrary nonfinite weights.

Preferred fix:

1. evaluate/compile the continuous connector for each candidate edge;
2. omit unavailable edges from weighted neighbor iteration;
3. cache finite actuator cost for admitted edges;
4. let Dijkstra/A* keep strict finite/nonnegative assertions.

Add an adapter-level failure record for visualization:

```text
candidate_edge_status: unavailable_local_motion
```

A disconnected query returns `found=False`. It does not become `planner_exception`.

## 10. Phase 7 — freeze the common-physical task bank before planners

Compute the exact intersection of all mounted usable Q boxes. Select starts and witness goals strictly inside that intersection. Map witness goals through the common planar robot to define X-space goal disks.

Preflight the complete bank across every mounted case before assigning the final digest. Freeze:

- task IDs and ordering;
- exact start Q and X;
- witness goal Q and X;
- goal radii;
- represented candidate IDs/order;
- seed and generator version;
- preflight matrix and digest.

The bank generator may fail and require a design edit **before** planner outcomes exist. Once a bank digest has planner outcomes, do not replace tasks under that digest.

The old V3.6B/V4.2A bank remains historical stress evidence and is not rerun as the V4.2B primary bank.

## 11. Phase 8 — retained data and manifest integrity

Avoid one oversized untracked JSONL. Prefer:

```text
geometry_atlas/cases/<case_id>/geometry_samples.jsonl.gz
```

Each file should be independently hashable and reviewable. The manifest should inventory itself through a stable root digest or exclude only itself from its file table with an explicit rule.

Provide a verifier callable from tests and CLI:

```bash
python scripts/verify_v4_2b_artifact.py \
  results/v4_review/v4_2b_span_controlled_corrective_closeout/
```

It should fail on:

- missing files;
- hash or byte-count mismatch;
- decompression failure;
- row-count mismatch;
- schema mismatch;
- unexpected required-file omissions.

## 12. Phase 9 — clean generation protocol

The generator must inspect source cleanliness before creating or deleting the output root:

```bash
git status --porcelain --untracked-files=all
```

Allow only an explicitly empty output root policy. Record the clean implementation HEAD as `source_git_revision` and `source_git_dirty: false`.

Recommended sequence:

```bash
git commit -am "Implement V4.2B corrective contracts"
git status --short   # must be empty
python scripts/generate_v4_2b_span_controlled_corrective.py
python scripts/verify_v4_2b_artifact.py results/v4_review/v4_2b_span_controlled_corrective_closeout/
git add results/v4_review/v4_2b_span_controlled_corrective_closeout docs/software/architecture/notes
git commit -m "Retain V4.2B corrective evidence and closeout"
```

The evidence commit is expected to differ from the recorded implementation revision. The manifest must make that lineage explicit rather than recording a dirty working-tree parent ambiguously.

## 13. Review checklist before closeout

### Coordinate review

- every mounted Q box is centered at zero;
- native Q plus/minus offsets reconstruct exactly;
- FK and `J_f` never consume native Q;
- `J_g` is unchanged by mounting.

### Geometry review

- 17 cases and two matrix memberships;
- 55,539 expected rows or typed failures;
- shared paired scales and identity control;
- no dropped samples.

### Planning review

- same physical tasks across cases;
- same node and edge IDs within each pair;
- no intersection-only fairness workaround;
- no nonfinite edge exceptions;
- failures remain visible.

### Artifact review

- every required file is tracked and hash-verified;
- source revision was clean;
- historical package digests unchanged;
- V4.3 points to V4.2B, not V4.2.

### Authorization review

- closeout returns to none;
- V4.3 remains unauthorized.

## 14. Stop conditions

Stop and request review rather than improvising when:

- applying the offset changes `J_g`;
- a mounted bound disagrees with the frozen range definition;
- the V3.6D digest changes;
- any historical package changes;
- shared paired topology cannot be made identical without changing the declared Q local-motion model;
- the common task bank has no feasible ten-task design inside the exact common mounted domain;
- a required retained file cannot fit the chosen repository storage contract;
- V4.3 code appears necessary to close V4.2B.
