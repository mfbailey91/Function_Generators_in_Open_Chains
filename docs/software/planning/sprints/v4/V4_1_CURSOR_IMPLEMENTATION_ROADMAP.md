# V4.1 Cursor Implementation Roadmap — Planar-2R Intrinsic Geometry Atlas

**Project:** Function Generators in Open Chains
**Sprint:** V4.1 — Planar-2R Intrinsic Geometry Atlas
**Reserved work packages:** V4-100–V4-108
**Execution style:** one bounded Cursor package at a time, with review gates between packages
**Evidence target:** `results/v4_review/v4_1_planar2r_geometry_atlas/`
**Planning status:** this guide does **not** activate V4.1 or authorize source work.

---

## 1. Purpose

Sprint V4.0 established one verified kinematic-transmission geometry kernel for

\[
\mathcal U \xrightarrow{g} \mathcal Q \xrightarrow{f} \mathcal X,
\]

with

\[
J_g=\frac{\partial q}{\partial u},\qquad
J_f=\frac{\partial x}{\partial q},\qquad
J_{xu}=J_fJ_g,
\]

\[
M_Q^{(U)}=J_g^{-\mathsf T}W_uJ_g^{-1},\qquad
B_Q^{(U)}=J_gW_u^{-1}J_g^\mathsf T,\qquad
B_X^{(U)}=J_{xu}W_u^{-1}J_{xu}^\mathsf T.
\]

V4.1 should **consume** that kernel and answer:

> Over one frozen shared-\(Q\) grid, what configuration, Jacobian, metric, mobility, and rank fields are induced by the canonical four-bar relative to span-matched and identity controls?

The execution ladder is:

\[
\boxed{
\text{Preflight}
\rightarrow
\text{V4-100}
\rightarrow
\text{V4-101}
\rightarrow
\text{V4-102}
\rightarrow
\text{V4-103}
\rightarrow
\text{V4-104}
\rightarrow
\text{V4-105}
\rightarrow
\text{V4-106}
\rightarrow
\text{V4-107}
\rightarrow
\text{V4-108}
}
\]

The sequence is intentionally:

1. protect the experiment;
2. freeze the data contract;
3. build records from the existing geometry kernel;
4. interpret only after representation is stable;
5. visualize only after the numerical contract is stable;
6. generate retained evidence only after regression passes.

---

## 2. Non-negotiable scientific contract

The atlas compares three arms on the **same output samples**:

1. canonical certified monotonic four-bar pair;
2. span-matched affine gearbox;
3. identity-on-shared-\(Q\) null control.

For every shared sample \(q^{(k)}\),

\[
q_F^{(k)}=q_G^{(k)}=q_I^{(k)},
\]

and therefore

\[
x_F^{(k)}=x_G^{(k)}=x_I^{(k)}=f(q^{(k)}).
\]

The actuator realizations may differ:

\[
u_F^{(k)}\neq u_G^{(k)}\neq u_I^{(k)}.
\]

Do **not** sample each mechanism independently in \(\mathcal U\) and pair nearby output states afterward.

Frozen study setup:

- four-bar: `a=1.0, b=2.5, c=2.0, d=2.0`;
- certified monotonic branches;
- span-matched gearbox using the accepted `span` convention;
- `Planar2R(L1=1.0, L2=1.0)`;
- \(W_u=I\);
- deterministic shared-\(Q\) grid;
- `33 x 33` atlas resolution unless the frozen config explicitly says otherwise;
- endpoint inset so inverse-defined quantities are not required exactly at the branch boundary.

Every retained report must state:

> **intrinsic geometry atlas; no mechanism performance inference.**

---

## 3. Kernel ownership rule

The V4.0 package

```text
src/inequality_mechanisms/transmission_geometry/
```

is authoritative for:

- \(J_{xu}=J_fJ_g\);
- tangent pushforward;
- covector pullback;
- rank reports;
- \(M_Q^{(U)}\);
- \(B_Q^{(U)}\);
- \(B_X^{(U)}\);
- inverse-metric availability;
- singularity semantics;
- geometry snapshot serialization.

V4.1 orchestration and visualization code must **not** create alternate implementations.

Useful review command after V4-103:

```bash
grep -R "np.linalg.inv\|pinv\|j_inv\|J_f.*@\|j_f.*@" \
  src/inequality_mechanisms/experiments/v4 \
  src/inequality_mechanisms/visualization/v4
```

Investigate any duplicated core differential math.

---

## 4. Explicit exclusions

V4.1 must not implement:

- differential IK;
- damped least-squares control;
- velocity polytopes;
- wrench polygons;
- static force optimization;
- potential functions or flow ODEs;
- application task banks;
- start/goal planning queries;
- mechanism populations or Monte Carlo;
- 3R or 6R;
- obstacles or collision studies;
- MoveIt;
- hardware;
- a scalar “better mechanism” score;
- rewriting frozen V1–V3 evidence;
- rewriting the V4.0 smoke package.

---

# 5. Preflight — merge V4.0 and activate V4.1 separately

## 5.1 Repository check

Before V4.1 implementation:

```bash
git status
git log --oneline --decorate -12
git branch --show-current
```

Confirm the accepted V4.0 closeout is on the branch from which V4.1 will be developed.

V4.0 closed at `c2e4452` on `Version_4_Kinematic_Transmission_Geometry`. That revision is **not** on `main`. Branch from the V4.0 closeout, not from `main`:

```bash
git checkout Version_4_Kinematic_Transmission_Geometry
git pull
git checkout -b v4_1_planar2r_geometry_atlas
```

## 5.2 Activation commit only

The activation commit should change planning/status documentation only.

Desired semantics:

```text
Current focus: Sprint V4.1
Code authorization: V4-100 through V4-108 only
V4.0: completed / frozen
V4.2+: unauthorized
Residual V3.7: unchanged / blocked unless separately authorized
```

Do **not** combine activation with source implementation.

### Cursor prompt — activation

> Review `SPRINT_V4_1_PLANAR2R_GEOMETRY_ATLAS.md`, `V4_PROJECT_PLAN.md`, ADR-027, the V4.0 closeout note, and `ACTIVE_SPRINT.md`. Do not implement source code yet. Prepare the minimal planning/status change required to activate only Sprint V4.1 work packages V4-100 through V4-108. Preserve V4.0 as completed evidence and preserve V4.2+, residual V3.7, 3R, 6R, obstacles, MoveIt, Monte Carlo, and deferred work as unauthorized. Show me the diff before making any implementation changes.

### Gate

Stop if the activation diff contains source, tests, results, V4.2 authorization, V3.7 authorization, or frozen-evidence changes.

---

# 6. Phase A — protect and freeze the experiment

## V4-100 — V4.1 artifact guard and V4.0 evidence freeze

### Goal

V4.1 may write only under:

```text
results/v4_review/v4_1_planar2r_geometry_atlas/
```

V4.1 writers must reject:

```text
results/v3_review/**
results/v4_review/v4_0_kinematic_geometry_core/**
results/v4_review/<any sibling package>/**
```

### Likely files

```text
src/inequality_mechanisms/audits/v4_artifact_guard.py
tests/v4/test_v4_1_artifact_guard.py
tests/v4/data/frozen_v4_0_smoke_digests.json
```

Prefer V4.1-specific guard functions:

```python
assert_v4_1_output_allowed(path)
prepare_v4_1_output_dir(path)
```

Add a required digest lock for retained V4.0 evidence, analogous to the V3 review lockfile. V4.1 may read V4.0 for regression but must not write it. After freeze, the canonical-path smoke generator must refuse `rmtree` / overwrite of `results/v4_review/v4_0_kinematic_geometry_core/`. Monkeypatched tmp roots may still exercise the historical V4.0 writer API.

### Tests

Cover:

- exact V4.1 root;
- nested allowed path;
- relative allowed path;
- V4.0 rejection;
- V3 rejection;
- sibling-V4 rejection;
- arbitrary outside path rejection.

### Cursor prompt — V4-100

> Implement only V4-100. Extend the Version 4 artifact guard for Sprint V4.1. V4.1 writers may write only under `results/v4_review/v4_1_planar2r_geometry_atlas/`. Treat the accepted V4.0 smoke package as frozen retained evidence and reject it as an output destination while permitting read-only regression access. Preserve every existing V3 freeze rule. Prefer V4.1-specific guard functions rather than weakening V4.0 semantics. Add focused tests for allowed nested paths, V4.0 rejection, V3 rejection, sibling-V4 rejection, and arbitrary-path rejection. Add a required digest lock for the retained V4.0 package. Refuse canonical-path regeneration of the V4.0 smoke root; tmp-root V4-008 tests may keep using a monkeypatched `REPO_ROOT`. Do not implement config, sampling, atlas records, visualization, or V4.2 work. Run only the relevant tests, then stop and show the diff and test output.

### Exit gate

| Destination | Expected |
| --- | --- |
| V4.1 atlas root | allow |
| child of V4.1 atlas root | allow |
| V4.0 smoke root | reject |
| V3 review package | reject |
| other V4 package | reject |
| arbitrary path | reject |

---

## V4-101 — frozen atlas configuration

### Goal

Freeze the experiment before creating data.

Add:

```text
configs/v4/planar2r_geometry_atlas_v1.json
```

and a Version 4-specific config model under:

```text
src/inequality_mechanisms/experiments/v4/
```

Do not overload the legacy V1 experiment schema unless a utility is truly shared and version-neutral.

Suggested structure:

```text
src/inequality_mechanisms/experiments/v4/
├── __init__.py
└── atlas_config.py
```

Freeze:

```text
schema_version
output_dir
canonical four-bar parameters
branch-selection policy
matching_rule = "span"
Planar2R L1/L2
actuator_weight = identity
rank-tolerance policy identifier
grid shape = [33, 33]
endpoint inset policy
deterministic generation
no_inference_statement
```

Use strict validation:

```python
model_config = ConfigDict(extra="forbid")
```

### Cursor prompt — V4-101

> Implement only V4-101. Add a strict Version 4-specific Pydantic config model under `src/inequality_mechanisms/experiments/v4/` and the frozen file `configs/v4/planar2r_geometry_atlas_v1.json`. Do not widen the legacy V1 experiment config schema unless a utility is truly version-neutral. Freeze the canonical crank-rocker `(1.0, 2.5, 2.0, 2.0)`, certified monotonic branch policy, span matching, Planar2R `(1.0, 1.0)`, identity actuator weight, the V4.0 rank policy, deterministic 33x33 shared-Q grid, explicit endpoint inset, V4.1 output root, and the no-inference statement. Forbid extra fields and reject incomplete configs. Add `tests/v4/test_v4_1_atlas_config.py`. Do not generate a sample grid or artifacts yet. Stop after showing the resolved config structure and focused test output.

### Exit gate

One frozen JSON file must completely determine the atlas setup without inspecting source defaults.

---

# 7. Phase B — build the shared atlas data model

## V4-102 — deterministic shared-\(Q\) sample bank

### Goal

Create one output-space sample bank:

\[
q^{(k)}\ \text{fixed first},
\]

then

\[
u_m^{(k)}=g_m^{-1}(q^{(k)}).
\]

Do not sample \(\mathcal U\) independently by mechanism.

### Suggested files

```text
src/inequality_mechanisms/experiments/v4/shared_q_atlas.py
tests/v4/test_v4_1_shared_q_grid.py
```

Suggested records:

```python
@dataclass(frozen=True, slots=True)
class SharedQSample:
    q_sample_id: str
    grid_index: tuple[int, int]
    q: tuple[float, float]
```

```python
@dataclass(frozen=True, slots=True)
class SharedQSampleBank:
    samples: tuple[SharedQSample, ...]
    shape: tuple[int, int]
    q_lower: tuple[float, float]
    q_upper: tuple[float, float]
    inset: tuple[float, float]
```

Stable IDs should derive from integer grid coordinates, not floating-point text:

```text
q_0000_0000
q_0000_0001
...
q_0032_0032
```

For `33 x 33`:

\[
N_Q=1089.
\]

### Cursor prompt — V4-102

> Implement only V4-102. Build a deterministic `SharedQSampleBank` from the certified four-bar output box and the frozen V4.1 config. Generate exactly one inset 33x33 Q grid with stable IDs based on integer grid coordinates. Do not use randomness. Do not sample U. Do not create one bank per mechanism. The exact same float Q vectors and IDs must later be consumed by four-bar, span-matched gearbox, and identity control. Fail if the configured inset empties or invalidates the domain. Add deterministic regeneration and ordering tests. Do not call `geometry_snapshot` and do not write result artifacts yet. Stop and show representative first/center/last samples and test output.

### Exit gate

Inspect first, center, and last samples. The bank must clearly be an output-space experiment.

---

## V4-103 — snapshot-backed atlas records

### Goal

Make every atlas row a consumer of the V4.0 kernel.

Suggested file:

```text
src/inequality_mechanisms/experiments/v4/geometry_atlas.py
```

Suggested envelope:

```python
@dataclass(frozen=True, slots=True)
class GeometryAtlasRow:
    schema_version: str
    mechanism_pair_id: str
    mechanism_id: str
    q_sample_id: str
    snapshot: KinematicGeometrySnapshot
    config_digest: str
    code_revision: str | None
```

Required pattern:

```python
candidate = robot.states_from_output(q)
snapshot = geometry_snapshot(robot, candidate.state)
```

The atlas layer may attach IDs, provenance, config digest, and code revision. It may not hand-code Jacobians, metrics, mobility, singular values, or rank.

Expected full cardinality if all three arms cover every sample:

\[
1089\times 3=3267.
\]

Failures must be explicit; never silently omit rows.

### Cursor prompt — V4-103

> Implement only V4-103. Add the atlas row/envelope model and conversion from a `SharedQSample` plus a V4-capable robot into a serialized V4.0 `geometry_snapshot`. The atlas layer must not calculate `J_g`, `J_f`, `J_xu`, actuator metrics, mobility, singular values, or rank itself. It may only call the existing V4.0 geometry snapshot API and serialize its result. Include `q_sample_id`, `mechanism_id`, `mechanism_pair_id`, config digest, and code revision. Preserve typed failures rather than dropping rows. Add round-trip and shared-Q/shared-X tests. Do not implement the three-arm factory, rank maps, HTML, or V4.2 work. Stop and show the new files, focused tests, and a grep demonstrating that core geometry formulas were not copied into the atlas layer.

### Exit gate

Run:

```bash
grep -R "np.linalg.inv\|pinv\|j_inv" \
  src/inequality_mechanisms/experiments/v4
```

Investigate any hit.

---

## V4-104 — canonical four-bar, span gearbox, and identity null control

### Goal

Construct three arms under one fairness contract.

Four-bar:

\[
q=g_F(u_F).
\]

Span gearbox:

\[
q=Ru_G.
\]

Identity control:

\[
u_I=q,\qquad J_g=I.
\]

The identity arm is a coordinate-null reference, not a third competitor.

### Suggested files

```text
src/inequality_mechanisms/experiments/v4/controls.py
tests/v4/test_v4_1_null_controls.py
```

Required invariants:

\[
q_F=q_G=q_I,
\]

\[
x_F=x_G=x_I.
\]

For identity and \(W_u=I\):

\[
M_Q^{(U)}=I,\qquad B_Q^{(U)}=I.
\]

Fail closed on span mismatch, incomplete shared-Q coverage, inverse failure, unequal \(x\), branch mismatch, or hidden resampling.

### Cursor prompt — V4-104

> Implement only V4-104. Add one factory that constructs the canonical certified four-bar arm, its ADR-012 span-matched affine gearbox arm, and an identity-on-shared-Q null control. All three consume the exact same `SharedQSampleBank`. Preserve mechanism-specific U states. The identity control uses `u=q`, `J_g=I`, and the same Planar2R forward kinematics at every shared Q sample. Record span ratios and matching provenance. Fail closed on Q-domain mismatch, inverse failure, branch mismatch, or unequal Cartesian pose for the same q_sample_id. Add analytic identity and span-control tests. Do not implement rank maps or visualization yet. Stop and show a small diagnostic table for several sample IDs containing q, u_fourbar, u_gearbox, u_identity, and x.

---

# 8. Phase C — interpret the geometry

## V4-105 — rank and singularity attribution

### Goal

Distinguish rank loss in:

\[
J_g,
\qquad
J_f,
\qquad
J_{xu}=J_fJ_g.
\]

Do not label every composite singularity as a transmission singularity.

Suggested file:

```text
src/inequality_mechanisms/experiments/v4/rank_fields.py
```

Build attribution from the snapshot's existing rank reports; do not recompute an alternate SVD policy.

Suggested record:

```python
@dataclass(frozen=True, slots=True)
class RankAttribution:
    transmission_full_rank: bool
    manipulator_full_rank: bool
    composite_full_rank: bool
    transmission_rank: int
    manipulator_rank: int
    composite_rank: int
    transmission_condition_number: float | None
    manipulator_condition_number: float | None
    composite_condition_number: float | None
    metric_status: str
```

Required test cases:

### Regular

```text
Jg: full
Jf: full
Jxu: full
```

### Manipulator singularity

```text
Jg: full
Jf: deficient
Jxu: deficient
actuator metric on Q may remain available
```

### Transmission singularity test double

```text
Jg: deficient
metric: unavailable
mobility: preserved where mathematically defined
```

### Cursor prompt — V4-105

> Implement only V4-105. Build rank/singularity field records strictly from each geometry snapshot's existing rank reports and metric status. Distinguish transmission rank loss (`J_g`), manipulator rank loss (`J_f`), and composite rank loss (`J_xu`). Never label a Planar2R singularity as a transmission singularity merely because `J_xu` is singular. Preserve inverse-metric unavailability explicitly. Add crafted tests for a regular state, a manipulator-singular state with full-rank transmission, and a rank-deficient transmission test double. Do not add pseudoinverses, damping, regularization, or solver logic. Stop with focused test output and three readable attribution records.

---

# 9. V4.0 carryover policy during V4.1

## State-tolerance authority

The snapshot/adapter tolerance seam identified at V4.0 closeout should not be casually changed during the atlas. V4.1 uses certified inverse-generated states, so the default policy is:

> Record the tolerance-authority cleanup as deferred hardening unless a real atlas failure shows it blocks V4.1.

If a fix becomes necessary, authorize it explicitly and add a dedicated regression test. The preferred later fix is to pass the declared tolerance through `jacobian_u_to_q(..., state_tolerance=)` rather than removing the snapshot override.

## `pullback_metric` SPD contract

`pullback_metric` currently checks shape and finiteness of a user-provided `target_metric` but does not apply the SPD contract already used for \(W_u\) via `validate_positive_definite`. Keep the name “metric”; do not generalize the operation to an arbitrary bilinear form. Do not SPD-check the pulled result: a rank-deficient Jacobian yields a positive-semidefinite pullback.

V4.1 uses \(W_u=I\) and kernel `actuator_metric_on_q`, so this does not block the atlas. Tighten the target-metric SPD check before Sprint V4.4 flow work.

## Deferred finite-difference helpers

V4-006 was deferred. V4.1 should not add a production finite-difference Jacobian API. Independent \(J_g\), \(J_f\), and \(J_{xu}\) validation belongs under tests in V4-107, including step-size notes and near-singular Planar2R samples. It is not a replacement for the 33×33 atlas.

---

## V4-106 — shared-scale HTML atlas and reproducible runner

### Goal

Create a reviewer-readable atlas **after** numerical records are stable.

Suggested layout:

```text
src/inequality_mechanisms/experiments/v4/
├── __init__.py
├── atlas_config.py
├── shared_q_atlas.py
├── geometry_atlas.py
├── controls.py
└── rank_fields.py

src/inequality_mechanisms/visualization/v4/
├── __init__.py
└── geometry_atlas.py

scripts/
└── generate_v4_1_planar2r_geometry_atlas.py
```

Retained output:

```text
results/v4_review/v4_1_planar2r_geometry_atlas/
├── manifest.json
├── resolved_config.json
├── geometry_samples.jsonl
├── rank_fields.json
├── index.html
└── figures/
```

### Required visual hierarchy

1. experiment contract and provenance;
2. \(q_i(u_i)\), \(u_i(q_i)\), \(dq_i/du_i\);
3. \(\sigma_{\min}(J_g)\), \(\sigma_{\max}(J_g)\);
4. \(\sigma_{\min}(J_f)\), \(\sigma_{\max}(J_f)\);
5. \(\sigma_{\min}(J_{xu})\), \(\sigma_{\max}(J_{xu})\);
6. \(M_Q^{(U)}\): \(\lambda_{\min}\), \(\lambda_{\max}\), \(\sqrt\kappa\), \(\sqrt{\det}\), sparse ellipses;
7. \(B_Q^{(U)}\) fields;
8. \(B_X^{(U)}\) descriptors and sparse task-space mobility ellipses;
9. rank-attribution maps for \(J_g\), \(J_f\), \(J_{xu}\), and metric availability.

Paired mechanism fields must use shared color limits. Do not independently auto-normalize the gearbox and four-bar.

The identity arm is a null control. Record the plotting rule so it does not accidentally distort paired interpretation.

### Development artifact policy

During V4-106 implementation, generate only disposable test output. Do not populate retained evidence until V4-107 passes.

### Cursor prompt — V4-106

> Implement only V4-106. Create the Version 4 atlas visualization package and reproducible runner. The runner must consume the frozen config, `SharedQSampleBank`, snapshot-backed atlas rows, controls, and rank records already implemented. Plotting code may derive visualization descriptors from stored snapshot values but may not recalculate Jg, Jf, Jxu, actuator metrics, mobility, or rank using alternate formulas. Produce the documented manifest/config/JSONL/rank/HTML structure and static print figures. Use shared scales for paired mechanism fields and clearly identify the identity arm as a null control rather than a third ranked competitor. Include transmission maps, Jg/Jf/Jxu singular-value fields, actuator-metric fields, mobility-on-Q fields, task-space mobility descriptors/ellipses, and rank-attribution maps. Every report must state `intrinsic geometry atlas; no mechanism performance inference.` During implementation, generate only disposable test output; do not yet write or commit the retained V4.1 evidence package. Stop with the temp report path, figure inventory, and focused tests.

---

# 10. Phase D — verification and retained evidence

## V4-107 — analytic controls, V4.0 regression, and full suite

### Control A — identity

For \(J_g=I\):

\[
M_Q^{(U)}=W_u.
\]

With \(W_u=I\):

\[
M_Q^{(U)}=I,\qquad B_Q^{(U)}=I.
\]

### Control B — span-matched gearbox

For

\[
J_g=\begin{bmatrix}r_1&0\\0&r_2\end{bmatrix},
\]

with \(W_u=I\):

\[
M_Q^{(U)}=
\begin{bmatrix}1/r_1^2&0\\0&1/r_2^2\end{bmatrix},
\]

\[
B_Q^{(U)}=
\begin{bmatrix}r_1^2&0\\0&r_2^2\end{bmatrix}.
\]

### Control C — direct V4.0 snapshot regression

For selected atlas samples, compare the retained row to a fresh direct call to:

```python
geometry_snapshot(...)
```

### Control D — retained V4.0 overlap

Where sample sets overlap or can be deterministically matched, compare:

```text
q
x
Jg
Jf
Jxu
rank reports
actuator metric
mobility on Q
mobility on X
metric status
```

without modifying V4.0.

### Control E — frozen evidence

Verify V3 digests and any V4.0 digest remain unchanged.

### Control F — independent finite differences

If useful, add a **test-only** helper for selected interior samples. Do not create a production Jacobian implementation.

### Test order

Run focused V4.1 tests first, then:

```bash
python -m pytest -q
```

### Cursor prompt — V4-107

> Implement only V4-107 and verification support. Add independent analytic controls for the identity and span-matched gearboxes, regress atlas rows against direct V4.0 `geometry_snapshot()` calls, and compare all deterministically overlapping samples against the retained V4.0 smoke package without modifying that package. Verify frozen V3 evidence remains unchanged and verify the required V4.0 digest lock. Add a test-only finite-difference helper and use it on selected interior Jg, Jf, and Jxu states, including a near-singular Planar2R sample and a step-size note in failure messages; do not create a production Jacobian implementation. Run the focused V4.1 tests first. If they pass, run the full regression suite. Do not generate or commit the final V4.1 evidence package yet. Stop with exact test counts, residual maxima, and any discrepancy.

### Exit gate

Do not generate retained evidence if an analytic control, direct snapshot regression, overlap regression, digest check, or full suite fails.

---

## V4-108 — generate once, inspect, freeze, close

### Commit A — implementation and tests

Commit V4-100 through V4-107 implementation first, for example:

```text
Implement V4.1 planar-2R intrinsic geometry atlas
```

Record:

```bash
git rev-parse HEAD
```

Then require a clean tree and passing tests:

```bash
git status
python -m pytest <focused V4.1 tests> -q
python -m pytest -q
```

### Generate retained evidence

Run one documented command, conceptually:

```bash
python scripts/generate_v4_1_planar2r_geometry_atlas.py \
  --config configs/v4/planar2r_geometry_atlas_v1.json \
  --output results/v4_review/v4_1_planar2r_geometry_atlas
```

The manifest must record the implementation revision used to generate the package.

### Manual visual review

Before accepting closeout, inspect:

1. Does \(J_f\) match across arms at the same \(q\)?
2. Is identity \(M_Q^{(U)}\) flat as expected?
3. Is span-gearbox \(J_g\) constant as expected?
4. Is four-bar \(J_g\) smooth over the certified branch?
5. Are \(M_Q^{(U)}\) and \(B_Q^{(U)}\) reciprocal on regular states?
6. Does \(B_X^{(U)}\) plausibly combine transmission and Planar2R geometry?
7. Are manipulator singularities attributed to \(J_f\), not incorrectly blamed on \(J_g\)?
8. Are paired color scales genuinely shared?
9. Are there branch/lifting discontinuities?
10. Are boundary effects separated from interior geometry?
11. Is ranking language absent?
12. Is identity visibly treated as a null reference rather than a third competitor?

### Commit B — evidence and closeout

Only after manual review, commit:

```text
results/v4_review/v4_1_planar2r_geometry_atlas/**
V4.1 closeout note
planning/status reset
```

Example:

```text
Record V4.1 planar-2R intrinsic geometry atlas evidence
```

Then reset:

```text
V4.1: completed
Code authorization: none
V4.2: unauthorized until separately reviewed and activated
```

### Cursor prompt — V4-108

> Implement only V4-108 closeout mechanics. Confirm the V4-100 through V4-107 implementation is committed and the working tree is clean. Run the focused V4.1 tests and the full regression suite. Generate the retained atlas exactly once from the recorded implementation revision using the frozen config and guarded V4.1 output root. Do not modify V4.0 or any frozen V3 evidence. Produce a concise closeout note recording implementation SHA, generation SHA if separate, config digest, artifact path, test counts, regression controls, and explicit no-inference disposition. Do not declare the sprint accepted solely because generation succeeds: stop after generation so the HTML can be manually reviewed. After explicit review approval, prepare the evidence/closeout commit and return `ACTIVE_SPRINT.md` to no code authorization. Do not activate V4.2.

---

# 11. Recommended Cursor cadence

Do **not** ask Cursor to implement V4-100 through V4-108 in one shot.

Preferred cadence:

```text
V4-100 -> review
V4-101 -> review
V4-102 -> review
V4-103 -> review
V4-104 -> review
V4-105 -> review
V4-106 -> review temporary atlas
V4-107 -> full verification
V4-108 -> retained generation + manual review + closeout
```

Practical commit grouping:

### Commit A — experiment contract

```text
V4-100
V4-101
V4-102
```

### Commit B — atlas semantics

```text
V4-103
V4-104
V4-105
```

### Commit C — report and verification

```text
V4-106
V4-107
```

### Commit D — retained evidence

```text
V4-108
```

---

# 12. Per-package Cursor review template

After every package, Cursor should stop and report:

```text
Work package:
Files changed:
New public APIs:
Existing APIs changed:
Tests added:
Tests run:
Test result:
Artifact files written:
Frozen files touched:
Assumptions:
Known follow-ups:
Scope not implemented:
```

If Cursor cannot fill out one of these fields, stop before proceeding.

---

# 13. Master Cursor context prompt

Use this once at the start of the implementation thread:

> We are implementing Sprint V4.1 incrementally. Read `SPRINT_V4_1_PLANAR2R_GEOMETRY_ATLAS.md`, ADR-027, `V4_PROJECT_PLAN.md`, `ACTIVE_SPRINT.md`, and the V4.0 closeout note before making changes. Treat the V4.0 `transmission_geometry` package as the authoritative mathematics. The atlas may orchestrate and visualize `geometry_snapshot` records but may not rederive transmission Jacobians, composite Jacobians, metrics, mobility, or rank semantics. The scientific comparison is one deterministic shared-Q grid applied to the canonical four-bar, its span-matched gearbox, and an identity-on-shared-Q null control. Q and X must match by sample ID; U and Jg may differ. V4.1 is descriptive and non-inferential. Preserve the V4.0 smoke package and all frozen V1–V3 evidence. Do not implement differential IK, velocity or wrench polytopes, potential flows, application tasks, Monte Carlo, 3R, 6R, obstacles, MoveIt, or hardware. Work only on the work package I explicitly name. After each package, stop and summarize files changed, tests run, assumptions made, artifacts written, frozen paths touched, and anything that would require widening scope.

Then begin with:

> **Implement V4-100 only.**

---

# 14. Expected scientific output

V4.0 established:

\[
\boxed{\text{the differential geometry implementation is trustworthy}}
\]

V4.1 should establish:

\[
\boxed{\text{the geometry induced by the canonical transmission over the shared robot domain is explicitly mapped}}
\]

At identical \(q\):

\[
\begin{array}{ccc}
\text{identity} & \text{span gearbox} & \text{four-bar}\\[4pt]
J_g=I & J_g=R & J_g=J_g(q)
\end{array}
\]

while

\[
J_f(q)
\]

is fixed by the same open-chain robot geometry.

The conceptual progression is:

\[
\boxed{\text{transmission}}
\rightarrow
\boxed{\text{configuration geometry}}
\rightarrow
\boxed{\text{task geometry}}.
\]

V4.1 stops at **description**. It does not yet ask whether the fields improve a particular application.

---

# 15. Definition of done

- [ ] V4.0 is retained and protected from V4.1 writes.
- [ ] V4.1 has one frozen config.
- [ ] One deterministic shared-\(Q\) bank is reused by all arms.
- [ ] The bank contains 1089 samples for a 33x33 grid.
- [ ] Every atlas row is backed by a V4.0 `geometry_snapshot`.
- [ ] Four-bar and span gearbox share \(q\) and \(x\) by `q_sample_id`.
- [ ] Identity control uses \(J_g=I\) on the same \(q\) samples.
- [ ] Span gearbox analytic controls pass.
- [ ] Identity analytic controls pass.
- [ ] Rank attribution distinguishes \(J_g\), \(J_f\), and \(J_{xu}\).
- [ ] No silent pseudoinverse is introduced.
- [ ] V4.0 overlap/direct-snapshot regressions pass.
- [ ] Frozen V3 evidence remains unchanged.
- [ ] V4.0 retained evidence remains unchanged.
- [ ] Shared-scale static atlas figures are reproducible.
- [ ] The HTML is explicitly non-inferential.
- [ ] The full regression suite passes.
- [ ] Retained evidence is generated from a recorded implementation revision.
- [ ] Manual visual review is completed before closeout acceptance.
- [ ] `ACTIVE_SPRINT.md` returns to no code authorization.
- [ ] V4.2 remains unauthorized until a separate reviewed activation.
