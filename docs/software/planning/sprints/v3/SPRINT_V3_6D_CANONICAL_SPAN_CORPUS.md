# Sprint V3.6D — Canonical Span Corpus

**Status:** completed; V3-650–V3-659 closed
**Reserved work packages:** V3-650–V3-659
**Depends on:** accepted V3.6C Gate A corrective closeout through V3-644; no-authorization repository state
**Blocks:** V3.6E, V3.6F, and architecture-final V3.7 activation
**Report target:** `results/v3_review/v3_6d_span_corpus/`
**Lineage note:** V4.1 described the legacy ~78° crank-rocker on a shared-Q atlas. This sprint synthesizes a new span-indexed family; it does not relabel or regenerate the V4.1 package.

## Sprint question

> Can we replace the single legacy mechanism with a deterministic, auditable family whose experimental factor is certified usable output span rather than an incidental link geometry?

## Frozen experimental factors

- robot: `Planar2R(L1=1,L2=1)`;
- Q centers: zero on both axes;
- core spans: `95,145,175` degrees;
- biological refinement spans: `135,145,150` degrees;
- one canonical four-bar per unique span;
- one matched constant transmission per four-bar;
- ordered 2R span assignments;
- old 78-degree linkage retained only in regression tests.

The two complete 3×3 ordered designs produce 17 unique cases after deduplicating `(145,145)`.

## Work packages

### V3-650 — Sprint contract and artifact guard

- activate only V3-650–V3-659;
- extend the artifact freeze guard for the D/E/F result lineages;
- add output-path refusal tests;
- add a program manifest scaffold.

### V3-651 — Span taxonomy and range schema

Introduce versioned records:

```python
@dataclass(frozen=True)
class OutputRangeDefinition:
    target_span_deg: float
    center_deg: float
    mechanical_interval_rad: tuple[float, float]
    usable_interval_rad: tuple[float, float]
    task_interval_rad: tuple[float, float] | None
    classification: Literal[
        "restricted_control",
        "biological_refinement",
        "central_biological_anchor",
        "near_limit_stress",
        "legacy_regression",
    ]
```

Validate:

- positive span;
- usable contained in mechanical;
- task contained in usable;
- consistent lifted chart;
- canonical zero-centered interval for this sprint.

### V3-652 — Deterministic canonical four-bar synthesis

Build a thin synthesis service over the existing `population.py` strict crank-rocker filters, `operating_branch.py` certification, `fourbar.py` kinematics, and `monotonic.py` branch tools. Do not duplicate those contracts. Add an orchestration service that accepts a target usable span and frozen certificate. Recommended API:

```python
synthesize_canonical_crank_rocker(
    target: OutputRangeTarget,
    certificate: MonotonicBranchCertificateProfile,
    objective: CanonicalSynthesisObjective,
    seed: int,
) -> CanonicalSynthesisResult
```

Requirements:

- normalized scale, e.g. `d=1`;
- strict crank-rocker/assembly filters;
- continuous lifted follower branch;
- target-span tolerance set before search;
- deterministic multi-start ordering;
- explicit infeasibility and boundary-stress statuses;
- no planner or wrench outcome in the objective;
- complete solver trace and rejected-candidate counts.

### V3-653 — Canonical registry and provenance

Create a versioned registry containing exactly one typed outcome for each target:

```text
95, 135, 145, 150, 175 degrees
```

Each record stores geometry, branch, intervals, certificate, descriptors, synthesis objective, seed, code revision, and content hash. Registry loading must verify the hash and refuse silent regeneration.

### V3-654 — Span-matched gearbox controls

Extend/reuse the existing `mechanisms/equivalence.py` span-matching path and `EquivalentGearbox`; do not add a second equivalence implementation. For every accepted four-bar, generate the constant map matching the same U/Q endpoints and average ratio. Tests must verify endpoint equality, average-gain equality, Q limits, and normalized actuator torque-limit parity.

### V3-655 — Ordered 2R case generator

Generate two study groups:

```text
core_span_sweep:          {95,145,175} × {95,145,175}
biological_refinement:    {135,145,150} × {135,145,150}
```

Deduplicate by ordered `(span_j1,span_j2)` while preserving membership tags. Assert 17 unique cases. Serialize deterministic IDs such as:

```text
span_j1_095_j2_175
span_j1_150_j2_135
```

### V3-656 — Mechanism characterization

For each axis produce:

- target, usable, and mechanical spans;
- selected U interval and average ratio;
- `min/max/mean/std(abs(dq_du))`;
- `min/max(abs(du_dq))` on finite certified samples;
- endpoint gains;
- gain-curvature or log-gain variation;
- change-point, branch, and endpoint margins;
- classification and certificate status.

Render one readable mechanism card per span and one table comparing the five canonical outcomes.

### V3-657 — Invariant and regression tests

Required tests:

1. deterministic synthesis under fixed profile/seed;
2. registry hash stability;
3. usable span within declared tolerance;
4. continuous monotonic lifted branch;
5. analytic/finite-difference Jacobian agreement;
6. inverse/forward round trip over usable Q;
7. equivalent gearbox endpoint and average-ratio match;
8. 17-case ordered union and membership tags;
9. legacy 78-degree fixture unchanged and absent from the scientific registry;
10. 175 typed behavior without certificate mutation.

### V3-658 — Config and exporter

Promote the planning seed config to an implementation-validated config and add the exporter:

```text
configs/v3/planar2r_span_wrench_program_v1.json
scripts/export_v3_6d_span_corpus.py
```

The exporter writes registry copies, descriptor JSON/CSV, mechanism cards, case matrix, provenance, and checksums.

### V3-659 — Clean generation and closeout

- implementation commit first;
- full tests;
- generate D artifact from clean revision;
- artifact commit separately;
- review every span card, especially 175;
- return `ACTIVE_SPRINT` to no authorization;
- do not auto-activate V3.6E.

## Proposed source targets

```text
src/inequality_mechanisms/
├── mechanisms/
│   ├── span_synthesis.py       # orchestration; reuse population/branch tools
│   ├── span_registry.py
│   ├── population.py           # extend only where a reusable filter is missing
│   ├── operating_branch.py     # reuse certificate; avoid parallel semantics
│   └── equivalence.py          # extend existing span-matched gearbox path
├── experiments/
│   └── span_cases.py
└── audits/
    └── span_corpus.py

configs/v3/planar2r_span_wrench_program_v1.json
scripts/export_v3_6d_span_corpus.py
tests/v3/test_v3_6d_span_corpus.py
```

## Exit criteria

1. The registry has five deterministic typed target outcomes.
2. All accepted mechanisms satisfy one predeclared primary certificate, or 175 is explicitly separated as boundary stress/unsupported.
3. The 17-case design is generated and auditable.
4. Every accepted four-bar has a matched gearbox.
5. Old evidence and the legacy fixture are unchanged.
6. The artifact is generated from a clean revision.
7. Repository returns to no authorization.
