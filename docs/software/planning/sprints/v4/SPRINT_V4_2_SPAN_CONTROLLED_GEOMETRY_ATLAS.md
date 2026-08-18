# Sprint V4.2 — Span-Controlled Mechanism Corpus and Geometry Atlas Extension

- **Status:** completed
- **Closeout:** [V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS_CLOSEOUT.md](../../../architecture/notes/V4_2_SPAN_CONTROLLED_GEOMETRY_ATLAS_CLOSEOUT.md)
- **Depends on:** closed V4.0; closed V4.1 (V4-100–V4-108); frozen V3.6D registry; no-authorization predecessor
- **Blocks:** V4.3 activation
- **Reserved work packages:** V4-200–V4-208
- **Does not reuse:** V4-100–V4-108
- **Artifact target:** `results/v4_review/v4_2_span_controlled_geometry_atlas/`
- **Cursor guide:** [CURSOR_GUIDE_POST_V4_1_SPAN_WRENCH_PROGRAM.md](../../CURSOR_GUIDE_POST_V4_1_SPAN_WRENCH_PROGRAM.md)

## Sprint purpose

Extend the V4.1 shared-\(Q\) geometry atlas from the legacy ~78° pair to the frozen V3.6D span family. Consume the hashed registry; do not resynthesize. Evaluate four-bar, span-matched gearbox, and identity-on-shared-\(Q\) at each of the 17 unique ordered assignments using V4.0 `geometry_snapshot`.

This sprint describes transmission geometry. It does not rank mechanisms, run application tasks, compute wrench polytopes, or retune certificates.

## Sprint question

> What intrinsic geometry fields does the certified span family induce on shared mounted \(Q\) grids, and how do they compare to span-matched affine controls and identity-on-shared-\(Q\)?

## Frozen inputs

- V3.6D package `results/v3_review/v3_6d_span_corpus/` (registry digest locked at implementation);
- V4.1 machinery in `src/inequality_mechanisms/experiments/v4/` and `visualization/v4/geometry_atlas.py`;
- V4.0 `geometry_snapshot`.

Cores \(\{95^\circ,145^\circ,175^\circ\}\) and bio \(\{135^\circ,145^\circ,150^\circ\}\) are already the D family. 175° remains `boundary_stress_only`. `PRIMARY_CERTIFICATE` is not mutated.

## Work packages

## V4-200 — Contract landing and artifact-guard extension

### Implementation

- Land this sprint and the program index link. Do not change `ACTIVE_SPRINT.md` in the planning commit.
- After activation, extend `v4_artifact_guard.py` so V4.2 writers may write only:

```text
results/v4_review/v4_2_span_controlled_geometry_atlas/
```

- Refuse V4.0, V4.1, every `results/v3_review/` package, sibling V4 packages, and arbitrary paths.

### Tests

- allowed nested V4.2 paths succeed;
- V4.0, V4.1, V3 packages, and arbitrary paths are refused.

### Exit

The atlas cannot overwrite historical evidence.

## V4-201 — Consume the frozen V3.6D registry

### Implementation

Load `results/v3_review/v3_6d_span_corpus/registry.json` by content digest. Do not call span synthesis. Record typed 175° status. Config must reject gravity/payload keys (`extra` forbid).

### Tests

- committed registry sha256 matches the frozen digest;
- 95/135/145/150 are `certified_primary`; 175 is `boundary_stress_only`;
- synthesis is not invoked on the V4.2 path.

### Exit

V4.2 is a consumer of D, not a second corpus.

## V4-202 — Seventeen generated cases and controls

### Implementation

Reuse `span_cases.py` membership generation. Preserve proximal/distal order. For each unique assignment attach:

- the V3.6D four-bar operating branch;
- a span-matched affine gearbox over the same usable U and Q intervals;
- identity-on-shared-\(Q\) (`experiments/v4/controls.py`), not ranked.

`(145,145)` has one physical record and two matrix placements.

### Tests

- 17 unique IDs; 18 labeled cells;
- `(95,175)` ≠ `(175,95)`;
- gearbox U/Q endpoints match the four-bar;
- identity \(J_g=I\) on the shared \(q\) samples.

### Exit

The case list is generated, not hand-authored.

## V4-203 — Per-case shared \(\eta\) grids

### Implementation

Reuse `shared_q_atlas.py`. Start from the V4.1 odd \(33\times 33\) inset policy. For each case

\[
q_i = c_i + \tfrac12 R_i\eta_i,\qquad \eta\in[-1,1]^2
\]

using that case’s mounted/usable centers and spans. Stable `q_sample_id` per case.

### Tests

- four-bar, gearbox, and identity receive identical `q` arrays within a case;
- inset excludes exact certified endpoints;
- generation is deterministic.

### Exit

Each case is a shared-\(Q\) experiment.

## V4-204 — Snapshot atlas records

### Implementation

Reuse `geometry_atlas.py`. Every row calls V4.0 `geometry_snapshot`. Serialize typed failures; do not drop samples.

### Tests

- row count = cases × grid samples × 3 arms, plus typed failure rows if any;
- snapshots carry `j_g`, `j_f`, `j_xu`, rank, and metric fields from the kernel.

### Exit

No local Jacobian fork.

## V4-205 — Rank attribution maps

### Implementation

Reuse V4.1 rank-field helpers. Attribute \(J_g\), \(J_f\), and \(J_{xu}\) separately, including 175° near-limit cases.

### Tests

- identity control is not treated as a four-bar singularity;
- serial-arm rank loss is distinguishable from transmission rank loss.

### Exit

Rank reports remain kernel-owned.

## V4-206 — Two-matrix HTML atlas

### Implementation

Root index shows core \(3\times 3\), biological \(3\times 3\), 175° classification, links to case pages, and a no-inference statement. Case pages use shared paired scales for four-bar/gearbox. Identity is a null-control panel. Static print panels are authoritative.

### Tests

- HTML contains the no-inference statement;
- 17 case pages exist;
- output directory is the V4.2 root.

### Exit

Reviewers can inspect geometry without ranking.

## V4-207 — Regression and freeze tests

### Implementation

Lock V3.6D registry digest and V4.1 package checksums. Prove V4.1 files are byte-unchanged after a V4.2 export.

### Tests

- D digest equality;
- V4.1 checksums unchanged;
- 17 unique IDs; 175 typed; identity \(J_g=I\).

### Exit

A later synthesis edit cannot silently drift V4.2 from D, and V4.1 stays frozen.

## V4-208 — Closeout and authorization reset

### Implementation

Write a closeout note. Return `ACTIVE_SPRINT.md` to no authorization. Do not activate V4.3 in the same commit.

### Exit

V4.2 evidence is retained. V4.3 requires a separate reviewed activation.

## Compact Cursor prompt

> Implement only Sprint V4.2 work packages V4-200–V4-208 after `ACTIVE_SPRINT.md` authorizes them. Preserve closed V4.0/V4.1 and frozen V3.6D–F. Consume the V3.6D registry by digest; do not resynthesize. Extend V4.1 shared-Q snapshot machinery to the 17 unique span assignments with span-matched gearboxes and identity-on-shared-Q. Call V4.0 `geometry_snapshot`. Write only `results/v4_review/v4_2_span_controlled_geometry_atlas/`. Do not implement V4.3, velocity, gravity, 3R, or MoveIt.
