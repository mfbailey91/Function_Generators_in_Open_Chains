# Sprint V4.2B — Span-Controlled Atlas Corrective Closeout

- **Status:** completed; canonical evidence retained; no current authorization
- **Depends on:** closed V4.2 and V4.2A; frozen V3.6D registry; closed V4.0 geometry kernel; no-authorization predecessor
- **Blocks:** V4.3 intrinsic static wrench and every downstream span-family column
- **Reserved work packages:** V4-220–V4-229
- **Does not reuse:** V4-200–V4-219 or V4-300–V4-309
- **Artifact target:** `results/v4_review/v4_2b_span_controlled_corrective_closeout/`
- **Architecture decision:** [ADR-029 — mounted output coordinates](../../../architecture/adr/ADR-029-mounted-output-coordinate.md)
- **Program amendment:** [V4_2B_CORRECTIVE_PROGRAM_AMENDMENT.md](../../V4_2B_CORRECTIVE_PROGRAM_AMENDMENT.md)
- **Cursor guide:** [V4_2B_CURSOR_IMPLEMENTATION_GUIDE.md](V4_2B_CURSOR_IMPLEMENTATION_GUIDE.md)

## Sprint purpose

Repair the span-family consumption, paired-graph, search-edge, retained-data, and provenance contracts exposed by review of V4.2 and V4.2A. Publish one fresh corrective package without rewriting historical evidence.

The primary defect is coordinate-level. V3.6D records a native four-bar follower interval, a zero-centered mounted output range, and the constant offset between them. V4.2/V4.2A reconstructed the native branch but passed its native follower angle directly into the planar robot. The resulting cross-span corpus changed output span **and** nominal robot posture.

V4.2B applies the recorded mounting at the consumer boundary:

\[
q_{\mathrm{joint}}=q_{\mathrm{native}}-q_{\mathrm{offset}},
\qquad
\frac{dq_{\mathrm{joint}}}{du}=\frac{dq_{\mathrm{native}}}{du}.
\]

This is not a mechanism resynthesis, a certificate retune, or a new population experiment.

## Sprint question

> After applying the frozen mounting offsets exactly once and restoring one shared paired graph contract, what intrinsic geometry and trial-scoped planning records does the certified span family produce on the intended robot joint coordinates?

## Historical disposition

The following packages remain immutable historical provenance:

```text
results/v4_review/v4_2_span_controlled_geometry_atlas/
results/v4_review/v4_2a_span_controlled_visual_audit/
```

They are not deleted, relabeled, or regenerated. V4.2B explains why they are unsuitable as the snapshot source for downstream cross-span wrench inference. After V4.2B closeout, V4.3 must consume the new V4.2B mounted-coordinate snapshots.

## Frozen inputs

- V3.6D registry and digest, including native geometry, branch sign, U intervals, `q_native_interval_rad`, `q_offset_rad`, zero-centered range definitions, and typed 175° status;
- V4.0 `geometry_snapshot` and rank/metric semantics;
- V4.1 shared-Q atlas machinery where compatible;
- V3.6B/V3.6C planner/result contracts where compatible;
- the 17 generated ordered span cases.

Do not call synthesis. Do not mutate `PRIMARY_CERTIFICATE`. Do not change 175° from `boundary_stress_only`.

## Corrected coordinate contract

For each axis, serialize and distinguish:

- `q_native`: four-bar solver follower coordinate;
- `q_offset`: frozen mounting offset;
- `q_joint`: physical mounted robot joint coordinate.

Only `q_joint` may populate `PhysicalState.q`, robot FK, `J_f`, `geometry_snapshot`, shared-Q grids, goals, and planning records. The native coordinate is diagnostic provenance.

The mounted branch must satisfy:

\[
[q_{\min},q_{\max}]
=
\texttt{range\_definition.usable\_interval\_rad},
\qquad
\frac{q_{\min}+q_{\max}}{2}=0.
\]

The span-matched affine gearbox is constructed against this mounted branch. Identity-on-shared-Q remains a geometry null control only.

## Corrected evidence package

Use one guarded root with two named subpackages:

```text
results/v4_review/v4_2b_span_controlled_corrective_closeout/
├── geometry_atlas/
├── planning_audit/
├── methods/
├── manifest.json
├── summary.json
├── index.html
└── README.md
```

### Geometry atlas

- 17 unique ordered cases;
- per-case odd `33 × 33` inset mounted-Q grid;
- four-bar, span-matched gearbox, and identity-on-shared-Q;
- V4.0 `geometry_snapshot` for every row;
- expected complete contract: `17 × 1089 × 3 = 55,539` rows;
- typed failures retained, never dropped;
- native coordinate and mounting offset recorded only in provenance.

### Corrected visual planning audit

The frozen V3.6B X-space bank remains historical stress evidence in V4.2A. V4.2B adds one new **common-physical span bank** frozen before planner outcomes:

- exact mounted `start_q` is identical across all 17 cases for a task;
- each goal disk is identical in X across all 17 cases;
- starts and witness goal configurations are selected from the exact intersection of all mounted usable Q boxes;
- the bank is preflighted across all 17 cases before its digest is frozen;
- five near and five far tasks retain the familiar trial-scoped audit size;
- no task is replaced after planner outcomes are observed.

Use the V3.6B planner families as diagnostic controls. Identity is not a planner arm. OMPL unavailability remains typed and does not block closeout. The audit is descriptive and non-inferential.

## Non-goals

- resynthesizing the span family or changing its registry digest;
- retuning primary or near-limit certificates;
- overwriting V4.2/V4.2A or any V3/V4 retained package;
- mechanism ranking, inferential statistics, or a hidden composite score;
- V4.3 wrench computation;
- velocity/IK, potential flow, gravity, payload, dynamics, friction, compliance, obstacles, 3R, 6R, or MoveIt;
- a range-normalized application study beyond the bounded common-physical audit bank.

## Work packages

## V4-220 — Corrective contract, ADR, and artifact guard

### Implementation

- Land ADR-029, this sprint, the program amendment, and the Cursor guide in a no-authorization planning commit.
- After separate activation, extend `v4_artifact_guard.py` with one allowed package:

```text
results/v4_review/v4_2b_span_controlled_corrective_closeout/
```

- Refuse writes into V4.0, V4.1, V4.2, V4.2A, all `results/v3_review/` packages, sibling V4 roots, and arbitrary paths.
- Add retained-package digests for V4.2 and V4.2A.

### Tests

- allowed root and nested paths succeed;
- every historical package and arbitrary path fails closed;
- tmp export leaves V4.2 and V4.2A byte-unchanged.

### Exit

The corrective sprint has one fresh output root and cannot rewrite its predecessors.

## V4-221 — Serializable mounted-output adapter

### Implementation

Add a focused mechanism/branch adapter, preferably under:

```text
src/inequality_mechanisms/mechanisms/output_mounting.py
```

Required behavior:

```python
q_joint = q_native - q_offset
q_native = q_joint + q_offset
J_mounted = J_native
```

Provide forward, inverse, Jacobian, bounds/certificate, output-space, and serialization support. Preserve assembly state, input space, and periodicity. A zero offset is an identity adapter.

Do not bake span-family offsets into `PlanarFourBar` or robot FK. The mounting is a reusable transmission-layer operation.

### Tests

- scalar and two-axis offsets;
- forward/inverse round trip;
- analytic Jacobian unchanged and finite-difference agreement;
- zero-offset identity;
- serialization round trip;
- double application is detectable or impossible by construction.

### Exit

Native mechanism coordinates and mounted robot coordinates are explicit and mechanically equivalent up to a constant offset.

## V4-222 — Frozen-registry mounted case realization

### Implementation

Update span-case realization to:

1. reconstruct the frozen native four-bars;
2. select/restore the recorded native operating intervals;
3. apply each stored `q_offset_rad` exactly once;
4. validate the mounted certificate against `range_definition.usable_interval_rad`;
5. construct the equivalent gearbox from the mounted branch;
6. retain native intervals and offsets in provenance.

Do not resynthesize or recertify under changed thresholds.

### Tests

For all five span records and all 17 cases:

- mounted midpoint is zero within tolerance;
- mounted width equals the frozen usable width;
- mounted bounds equal the registry range definition;
- gearbox U/Q endpoints equal the mounted four-bar endpoints;
- mounted and native `J_g` agree;
- 175° remains typed `boundary_stress_only`.

### Exit

Every realized case represents the intended robot posture and the frozen native mechanism.

## V4-223 — Corrected mounted-Q geometry atlas

### Implementation

Add a strict V4.2B config and generator. Reuse the V4.1/V4.2 shared-Q and HTML machinery only after replacing native-Q assumptions with mounted-Q records. Every mechanism row calls V4.0 `geometry_snapshot`.

Write per-case compressed data files rather than one oversized untracked JSONL. Use stable mounted-Q sample IDs and preserve the two-matrix case memberships.

### Tests

- deterministic `33 × 33` inset samples;
- identical mounted Q and X across the three geometry arms within a case;
- identity `J_g = I`;
- rank attribution remains separate for `J_g`, `J_f`, and `J_xu`;
- expected row count or typed failure rows, with zero silent drops.

### Exit

The corrected intrinsic atlas varies span/mechanism geometry without an accidental native-angle posture shift.

## V4-224 — One shared paired planning topology

### Implementation

Replace post-hoc edge-set intersection with one common-Q planning graph construction:

1. generate one Q sample bank and candidate adjacency per case;
2. inverse-lift each sample through both paired mechanisms;
3. compute one shared validity mask before graph construction;
4. freeze one node-ID set and one edge-ID set;
5. embed that topology separately in each mechanism's U coordinates;
6. integrate mechanism-specific actuator costs on the same declared Q local motions.

If pair invariants fail, abort the case with typed `paired_topology_mismatch`. Do not continue with an intersection-only primary comparison. Preserve rejected-node/edge diagnostics separately.

### Tests

For every case at smoke and production shapes:

```text
fourbar_node_ids == gearbox_node_ids
fourbar_edge_ids == gearbox_edge_ids
q_fourbar == q_gearbox
x_fourbar == x_gearbox
```

### Exit

The paired planning comparison holds topology and visible local motion fixed.

## V4-225 — Invalid local motion and finite search-edge contract

### Implementation

Resolve the contradiction between connector failure and generic graph search:

- a failed continuous connector means the candidate adjacency is not an available planning edge;
- compile/filter such edges before search;
- `neighbors(node)` presented to Dijkstra/A* yields only available finite nonnegative edges;
- generic search remains strict and rejects NaN, negative, or accidentally nonfinite supplied weights;
- diagnostic edge metrics may record `unavailable`, but search must never receive `+inf` as an ordinary edge cost.

### Tests

- one invalid edge plus one finite route solves through the finite route;
- all-invalid routes return ordinary `found=False`, not a planner exception;
- Dijkstra and A* agree on optimal cost;
- no V4.2B row has `planner_exception` caused by nonfinite lattice cost.

### Exit

Invalid local motions are graph exclusions, not search-core crashes.

## V4-226 — Common-physical task bank and corrected visual audit

### Implementation

Create a deterministic config and task bank, for example:

```text
configs/v4/span_common_physical_planar2r_v1.json
configs/v4/planar2r_span_controlled_corrective_audit_v1.json
```

Derive the exact common mounted-Q box from all 17 supported cases. Freeze ten tasks before planner execution. Each task stores exact shared `start_q`, witness goal `q`, start X, goal X/disk, residual policy, candidate IDs, and bank digest.

Generate trial-scoped pages with:

- the same physical task across every case;
- four-bar/gearbox pair only;
- common topology for lattice planners;
- failures and OMPL unavailability retained;
- no ranking or inferential language.

The legacy V3.6B bank is not regenerated here; link V4.2A as historical stress evidence.

### Tests

- all ten tasks preflight successfully across all 17 mounted cases;
- exact `start_q`, start X, goal center, goal radius, and represented candidate ordering are case-invariant;
- no task replacement after outcome inspection;
- HTML labels the bank `common_physical_span_bank_v1` and states the no-inference contract.

### Exit

The corrective visual audit compares the same physical tasks rather than per-case re-authored starts and largely unreachable legacy goals.

## V4-227 — Complete retained-data and manifest contract

### Implementation

Store the complete primary rows in tracked, retrievable compressed files, preferably one `jsonl.gz` per case. The root manifest must inventory every required file with:

```text
path
sha256
byte_count
row_count
schema_version
media_type
compression
```

No manifest-required file may be omitted by `.gitignore` or exceed the selected repository storage policy. Add a clean-checkout integrity verifier.

### Tests

- every manifest-listed path exists;
- every SHA-256, byte count, and row count matches;
- decompression and schema parsing succeed;
- the complete geometry row count is recoverable from tracked files;
- a missing or mutated file fails closed.

### Exit

The retained evidence package is self-contained and auditable from a clean checkout.

## V4-228 — Cross-package regression and clean-source provenance

### Implementation

Add an all-case corrective regression suite. The generator must refuse a dirty source tree **before** creating outputs and record:

```text
source_git_revision
source_git_dirty: false
config_digest
v3_6d_registry_digest
schema versions
```

Use separate implementation and evidence commits. Capture the implementation commit as the generation source; commit generated evidence afterward.

### Tests

- V3.6D registry digest unchanged and synthesis functions not called;
- V4.0/V4.1/V4.2/V4.2A and V3 retained-package digests unchanged;
- all mounted-coordinate and shared-topology invariants pass;
- no required artifact is absent;
- dirty-source generation is refused;
- source revision is an ancestor of the evidence commit.

### Exit

The correction is reproducible, traceable, and does not silently alter historical evidence.

## V4-229 — Full generation, independent review, and authorization reset

### Implementation

1. Commit implementation/tests/configs with no generated V4.2B evidence present.
2. Run focused tests, all V4 tests, and the full regression suite.
3. From that clean implementation commit, generate the complete V4.2B package.
4. Review geometry, topology, failure tables, common-task pages, and manifest integrity.
5. Commit evidence and a V4.2B closeout/review note.
6. Update downstream planning so V4.3 consumes V4.2B snapshots.
7. Return `ACTIVE_SPRINT.md` to no authorization.

Do not activate V4.3 in the closeout commit.

### Exit

V4.2B is the canonical span-family snapshot source. V4.3 remains a separate reviewed activation.

## Sprint exit criteria

V4.2B closes only when all are true:

1. every supported axis realizes the exact zero-centered mounted output interval;
2. the V3.6D registry digest and synthesis certificates are unchanged;
3. the corrected geometry atlas contains all 17 cases and all expected rows or typed failures;
4. every paired planning case has identical node IDs and edge IDs across mechanisms;
5. invalid local motions never enter search as `+inf` edges;
6. the common-physical task bank is frozen and feasible across all 17 cases;
7. no nonfinite lattice-cost planner exception remains;
8. every required retained data file is tracked, retrievable, and hash-verified;
9. generation records a clean source revision and uses separate implementation/evidence commits;
10. V4.0/V4.1/V4.2/V4.2A and every frozen V3 package are byte-unchanged;
11. the closeout states that V4.2/V4.2A remain historical and V4.2B is the downstream source;
12. authorization returns to none without activating V4.3.

## Compact Cursor prompt

> Implement only Sprint V4.2B work packages V4-220–V4-229 after `ACTIVE_SPRINT.md` authorizes them. Preserve and do not regenerate V4.0, V4.1, V4.2, V4.2A, and all V3 retained evidence. Consume the frozen V3.6D registry by digest; do not resynthesize or retune certificates. Apply each recorded output mounting offset exactly once so `PhysicalState.q`, FK, `J_f`, shared-Q samples, and goals use zero-centered mounted robot joint coordinates while native follower coordinates remain provenance. Rebuild the 17-case V4.0 snapshot atlas under the fresh V4.2B root. Use one common paired Q topology, filter invalid local motions before search, freeze a common-physical cross-span task bank, retain complete compressed row data with hashes, and generate from a clean implementation commit. Do not implement V4.3, gravity, velocity, 3R, obstacles, 6R, or MoveIt.
