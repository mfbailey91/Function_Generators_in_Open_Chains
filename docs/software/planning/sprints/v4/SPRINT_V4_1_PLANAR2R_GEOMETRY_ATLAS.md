# Sprint V4.1 — Planar-2R Intrinsic Geometry Atlas

- **Status:** drafted / blocked until Sprint V4.0 closes and `ACTIVE_SPRINT.md` separately authorizes V4-100–V4-108
- **Activation dependency:** V4-001–V4-009 implemented; Gate V4-A closed; explicit active-sprint change
- **Reserved work packages:** V4-100–V4-108
- **Initial mechanism scope:** canonical certified monotonic crank-rocker pair, span-matched affine gearbox, and identity-gearbox null control
- **Initial robot scope:** planar 2R
- **Fresh artifact target:** `results/v4_review/v4_1_planar2r_geometry_atlas/`

## 1. Sprint purpose

Build the first Version 4 **intrinsic atlas**: a dense, paired description of what the canonical planar-2R transmissions induce over one shared \(Q/X\) domain.

The atlas consumes the V4.0 geometry kernel rather than rederiving it. At each shared output sample it records the certified physical state and the kernel snapshot

\[
J_g=\frac{\partial q}{\partial u},
\qquad
J_f=\frac{\partial x}{\partial q},
\qquad
J_{xu}=J_fJ_g,
\]

\[
M_Q^{(U)}=J_g^{-\mathsf T}W_uJ_g^{-1},
\qquad
B_Q^{(U)}=J_gW_u^{-1}J_g^\mathsf T,
\qquad
B_X^{(U)}=J_{xu}W_u^{-1}J_{xu}^\mathsf T,
\]

together with rank reports and the V3-636 ellipse descriptors.

This sprint describes the transmission without judging it. It does not run application tasks, inverse-kinematics solvers, wrench polytopes, potential-flow ODEs, or Monte Carlo.

The V4.0 smoke grid (planned \(17\times 17\)) remains a kernel-verification artifact. V4.1 is a denser field atlas on the same frozen pair.

## 2. Sprint question

> Over one frozen shared-\(Q\) grid, what configuration, Jacobian, metric, mobility, and rank fields does the canonical four-bar induce relative to span-matched and identity gearbox controls?

## 3. Required design outcomes

By sprint close:

1. One frozen atlas config names the pair, kinematics, \(W_u\), rank policy, grid, and no-inference statement.
2. One deterministic shared-\(Q\) sample bank is reused by every mechanism arm.
3. Every atlas row is a serialized V4.0 `geometry_snapshot` keyed by `q_sample_id` and `mechanism_id`.
4. The span-matched gearbox shares the four-bar \(Q\) box; the identity gearbox is a coordinate-null control on the same \(q\) samples, not a third competitor.
5. Rank loss is attributed separately to \(J_g\), \(J_f\), and \(J_{xu}\).
6. A shared-scale HTML atlas shows the fields without a mechanism-performance claim.
7. Analytic gearbox and interior four-bar samples agree with the V4.0 kernel; overlapping V4.0 smoke samples regress within tolerance.

## 4. Target source tree

Only the following new paths are authorized when V4.1 becomes active:

```text
src/inequality_mechanisms/experiments/v4/
src/inequality_mechanisms/visualization/v4/
configs/v4/planar2r_geometry_atlas_v1.json
scripts/generate_v4_1_planar2r_geometry_atlas.py
```

Expected existing-file touch points:

```text
src/inequality_mechanisms/audits/v4_artifact_guard.py
src/inequality_mechanisms/transmission_geometry/snapshot.py
```

Expected tests:

```text
tests/v4/test_v4_1_atlas_config.py
tests/v4/test_v4_1_shared_q_grid.py
tests/v4/test_v4_1_snapshot_records.py
tests/v4/test_v4_1_null_controls.py
tests/v4/test_v4_1_rank_fields.py
tests/v4/test_v4_1_artifact_guard.py
```

Do not create `differential_ik/`, `capabilities/`, or `flows/` during this sprint.

## 5. Frozen pair and fairness contract

Reuse the accepted V3.6B/C representative pair so the atlas sits on existing evidence:

- crank-rocker \(a=1.0\), \(b=2.5\), \(c=2.0\), \(d=2.0\), certified monotonic branches;
- span-matched equivalent gearbox (ADR-012 span rule);
- `Planar2R(L1=1, L2=1)`;
- common bounded \(Q\) domain from the certified four-bar branches.

All arms must share:

- the same \(q\) samples and sample identifiers;
- the same Cartesian poses \(x=f(q)\);
- the same actuator weight, initially \(W_u=I\);
- the same rank-tolerance policy as V4.0;
- the same grid inset margin.

Four-bar and span-matched gearbox keep distinct actuator states \(u\). Identity control uses \(J_g=I\) at the same \(q\) samples. Fail closed if the span-matched gearbox does not cover the four-bar \(Q\) box, or if two arms report different \(x\) at the same `q_sample_id`.

No pooled table may hide mechanism-specific rank loss or inverse-metric unavailability. Failures remain in the package.

## 6. Included and excluded fields

### 6.1 Included at each sample

- \(u\leftrightarrow q\) and \(x=f(q)\);
- \(J_g\), \(J_f\), \(J_{xu}\) with singular values and rank reports;
- \(W_u\), \(M_Q^{(U)}\) or a typed unavailability status, \(B_Q^{(U)}\), \(B_X^{(U)}\);
- ellipse descriptors already used by V3-636: \(\lambda_{\min}\), \(\lambda_{\max}\), \(\sqrt{\kappa}\), \(\sqrt{\det}\).

Task-space mobility ellipses from \(B_X^{(U)}\) are kernel fields and belong in this atlas.

### 6.2 Explicitly excluded

- velocity polytopes, actuator-rate boxes, damped IK, and tracking (V4.2);
- wrench polygons and force-margin optimization (V4.3);
- potential functions, ODE integration, and basin maps (V4.4);
- application task banks and start/goal queries (V4.5);
- mechanism ranking or a scalar “better” score;
- regenerating frozen Version 1–3 packages.

## 7. Null controls

1. **Span-matched affine gearbox.** Fair paired comparison on the same \(Q\) box. Record the matched ratio per axis and the ADR-012 matching provenance.
2. **Identity gearbox** \(J_g=I\) on the same \(q\) samples. Coordinate-null control that shows the open-chain geometry with no transmission shaping. It is not a third competitor in any ranking table.

The unit-gearbox \(q=u\) map is not a substitute for the identity-on-shared-\(Q\) control when the four-bar \(Q\) box is not the identity input box.

## 8. Work packages

## V4-100 — Contract landing and artifact-guard extension

### Implementation

- Land this sprint document and the V4 sprint-index link.
- Do not change `ACTIVE_SPRINT.md` in the planning commit.
- When the sprint is later activated, extend the Version 4 artifact guard so V4.1 writers may write only under:

```text
results/v4_review/v4_1_planar2r_geometry_atlas/
```

- Continue to refuse every `results/v3_review/` package and every other `results/v4_review/` package, including the V4.0 smoke root unless a test explicitly reads it.

### Tests

- planning commit changes no source or frozen result file;
- after activation, the V4.1 runner refuses frozen V3 paths and unauthorized V4 packages;
- the fresh V4.1 directory can be created from a clean tree.

### Exit

The atlas cannot overwrite historical evidence.

## V4-101 — Frozen atlas configuration

### Implementation

Add:

```text
configs/v4/planar2r_geometry_atlas_v1.json
```

The config must freeze:

- pair geometry and branch policy;
- span-matching rule `span`;
- `Planar2R` lengths;
- \(W_u=I\);
- rank-tolerance policy identifier from V4.0;
- grid shape `33 x 33` and a declared endpoint inset margin;
- seed if any stochastic helper is used (default: none; generation is deterministic);
- `no_inference_statement`.

### Tests

- config schema rejects missing pair, kinematics, weight, or output-dir fields;
- declared output directory is the V4.1 artifact root;
- statement forbids ranking and inferential statistics.

### Exit

Reviewers can regenerate the atlas from one frozen file.

## V4-102 — Deterministic shared-\(Q\) grid

### Implementation

Generate one shared output sample bank:

- shape `33 x 33` unless the frozen config records a different odd shape;
- samples lie in the certified four-bar \(Q\) box;
- endpoints are inset by the declared margin so inverse-defined metrics are not required at the exact branch boundary;
- each sample has a stable `q_sample_id`.

Do not sample independently in \(U\) and then attempt to pair nearest \(q\) values.

### Tests

- four-bar, span-matched gearbox, and identity control receive identical `q` arrays;
- sample identifiers are stable under regeneration;
- inset margin excludes the exact certified endpoints;
- grid generation is deterministic.

### Exit

The atlas is a shared-\(Q\) experiment, not three similar-looking clouds.

## V4-103 — Snapshot atlas records

### Implementation

For each `(q_sample_id, mechanism_id)` call the V4.0 snapshot builder. Serialize one JSONL (or equivalent) record containing:

- schema version;
- `q_sample_id`, `mechanism_id`, `mechanism_pair_id`;
- the V4.0 geometry snapshot;
- config digest and code revision.

Do not copy Jacobian or metric formulas into the atlas generator.

### Tests

- each record round-trips through the V4.0 snapshot serializer;
- four-bar and gearbox snapshots at the same `q_sample_id` share `q` and `x` and differ in `u` and \(J_g\);
- identity-control \(J_g\) is the identity at full rank;
- missing snapshots are typed failures, not omitted rows.

### Exit

Later columns can join this atlas by `q_sample_id` without rebuilding the grid.

## V4-104 — Identity and span-matched controls

### Implementation

Construct:

1. the certified four-bar operating-branch robot;
2. the span-matched affine gearbox robot on the same \(Q\) box;
3. the identity control on the same \(q\) samples.

Record matched ratios and matching provenance. Fail closed on span mismatch, inverse failure, or unequal \(x\).

### Tests

- span-matched \(J_g\) is the recorded diagonal ratio;
- identity \(J_g=I\) and \(M_Q^{(U)}=W_u\) on regular samples;
- a deliberately mismatched \(Q\) box raises rather than silently resampling.

### Exit

Null controls are explicit and testable.

## V4-105 — Rank and singularity attribution maps

### Implementation

From each snapshot, store field maps for:

- `full_rank` and numerical rank of \(J_g\), \(J_f\), and \(J_{xu}\);
- condition numbers where defined;
- `metric_status` / inverse-metric availability.

Composite rank loss may not be labeled a transmission singularity when only \(J_f\) is rank-deficient. Near-workspace-boundary Planar2R samples must remain distinguishable from transmission rank loss.

### Tests

- interior four-bar samples are transmission-full-rank on this certified branch;
- a crafted near-stretched Planar2R sample attributes rank loss to \(J_f\) or \(J_{xu}\), not automatically to \(J_g\);
- inverse-metric unavailability is serialized, not filled with a pseudoinverse.

### Exit

The atlas can explain where geometry becomes undefined before later solvers are written.

## V4-106 — Shared-scale HTML atlas

### Runner

Add:

```text
scripts/generate_v4_1_planar2r_geometry_atlas.py
```

### Outputs

```text
results/v4_review/v4_1_planar2r_geometry_atlas/
├── manifest.json
├── resolved_config.json
├── geometry_samples.jsonl
├── rank_fields.json
└── index.html
```

The HTML must show, on shared color and axis scales:

- \(q_i(u_i)\) and \(dq_i/du_i\) for four-bar and span-matched gearbox;
- singular values of \(J_g\), \(J_f\), and \(J_{xu}\);
- eigenvalues / \(\sqrt{\kappa}\) / \(\sqrt{\det}\) of \(M_Q^{(U)}\) and \(B_Q^{(U)}\);
- \(B_X^{(U)}\) ellipse descriptors;
- rank-attribution maps;
- explicit statement: “intrinsic geometry atlas; no mechanism performance inference.”

Static print panels are authoritative.

### Exit

A reviewer can inspect the fields without treating the atlas as a ranking study.

## V4-107 — Analytic controls and V4.0 regression

### Tests

- identity and span-matched analytic \(J_g\), \(M_Q^{(U)}\), and \(B_Q^{(U)}\) identities from Sprint V4.0 §7.1;
- interior four-bar snapshots match fresh V4.0 `geometry_snapshot` calls;
- any sample also present in the V4.0 smoke grid agrees within the frozen residual tolerance;
- the complete existing regression suite still passes;
- frozen V3 package digests are unchanged.

### Exit

The atlas is a consumer of the kernel, not a second implementation.

## V4-108 — Closeout and authorization reset

### Review checklist

- all V4.1 tests pass from a clean environment;
- full existing regression suite passes;
- no frozen result digest changes;
- atlas artifact is regenerated from the recorded implementation revision;
- no silent pseudoinverse appears in atlas code;
- V4.2 remains unauthorized.

### Commit separation

Use two commits when evidence is retained:

1. implementation and tests;
2. generated V4.1 atlas evidence and closeout notes.

### Exit

Return `ACTIVE_SPRINT.md` to no authorization or activate V4.2 through a separate reviewed change. V4.1 completion must not automatically authorize later sprints.

## 9. Commands after activation

The implementation should support a bounded command sequence resembling:

```bash
python -m pytest tests/v4/test_v4_1_atlas_config.py tests/v4/test_v4_1_shared_q_grid.py tests/v4/test_v4_1_snapshot_records.py tests/v4/test_v4_1_null_controls.py tests/v4/test_v4_1_rank_fields.py tests/v4/test_v4_1_artifact_guard.py -q
python -m pytest -q
python scripts/generate_v4_1_planar2r_geometry_atlas.py \
  --config configs/v4/planar2r_geometry_atlas_v1.json \
  --output results/v4_review/v4_1_planar2r_geometry_atlas
```

Exact command-line options may follow repository conventions, but one documented command must reproduce the atlas package.

## 10. Failure taxonomy

At minimum:

- `invalid_physical_state`;
- `q_domain_mismatch`;
- `span_match_failed`;
- `unequal_shared_pose`;
- `transmission_rank_deficient`;
- `manipulator_rank_deficient`;
- `composite_rank_deficient`;
- `inverse_metric_unavailable`;
- `artifact_path_forbidden`.

Failures are results or typed exceptions. Do not convert mathematical failure into `NaN`-filled success records.

## 11. Sprint exclusions

V4.1 must not:

- implement V4.0 kernel APIs that do not yet exist; wait for V4-001–V4-009;
- implement a Jacobian inverse or damped least-squares controller;
- construct velocity or wrench polygons;
- integrate a potential-flow ODE;
- add application task banks;
- run mechanism populations or Monte Carlo;
- modify V3 planning estimands;
- activate V3.7, 6R, obstacles, MoveIt, or hardware work;
- overwrite any Version 1–3 evidence or the V4.0 smoke package.

## 12. Definition of done

Sprint V4.1 is complete only when:

1. the frozen pair, shared \(Q\) grid, and null controls match this contract;
2. every atlas row is a V4.0 snapshot rather than a locally rederived Jacobian or metric;
3. rank attribution distinguishes transmission and manipulator singularities;
4. the HTML atlas is reproducible, shared-scale, and explicitly non-inferential;
5. analytic gearbox identities and overlapping V4.0 samples pass;
6. the complete regression suite passes;
7. `ACTIVE_SPRINT.md` does not automatically authorize V4.2.

## 13. Cursor handoff prompt

> Implement only Sprint V4.1 work packages V4-100–V4-108 after confirming Sprint V4.0 is closed and `ACTIVE_SPRINT.md` explicitly authorizes them. Preserve all frozen Version 1–3 result packages and the V4.0 smoke artifact. Add a frozen planar-2R atlas config, a deterministic shared-\(Q\) `33 x 33` grid with endpoint inset, and atlas records that serialize V4.0 geometry snapshots for the canonical crank-rocker, its span-matched gearbox, and an identity-on-shared-\(Q\) null control. Do not rederive \(J_{xu}\) or \(M_Q^{(U)}\). Emit rank-attribution maps and a shared-scale non-inferential HTML atlas under `results/v4_review/v4_1_planar2r_geometry_atlas/`. Extend the V4 artifact guard to that directory only. Do not implement V4.2 or any differential-IK, wrench-polytope, flow-ODE, Monte Carlo, 3R, 6R, obstacle, or MoveIt work.
