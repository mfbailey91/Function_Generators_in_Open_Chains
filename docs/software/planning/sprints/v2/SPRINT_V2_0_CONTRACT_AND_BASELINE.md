# Sprint V2.0 — Contract and Baseline Preservation

## Theme

> Change the research question without losing the evidence already produced.

## Objective

Freeze the Version 2 scientific and architectural contract, preserve the accepted Version 1 full-cycle formulation, remove conflicting agent instructions, and establish deterministic golden fixtures before any implementation rearchitecture begins.

This sprint is primarily documentation and test-fixture work. It is intentionally completed before search, mechanism, or graph APIs are changed.

## Inputs

- `docs/software/PROJECT_PLAN.md`
- `docs/software/architecture/adr/ADR-001-search-in-input-space.md`
- `docs/software/architecture/adr/ADR-011-output-space-semantics.md`
- `docs/software/planning/sprints/v1/SPRINT_FOUR_BACKLOG.md`
- `.cursor/rules/project.mdc`
- current Version 1 pilot and deterministic test configurations

## Decisions to freeze

1. Version 1 remains valid for noninjective/full-cycle mechanisms.
2. Version 2 uses only certified, one-to-one operating branches.
3. Version 2 planning state identity lives in \(\mathcal Q\).
4. The unique actuator realization \(\mathbf u=g^{-1}(\mathbf q)\) is attached node data.
5. Version 2 branch topology is nonperiodic.
6. Uniform-\(\mathcal U\) and uniform-\(\mathcal Q\) are separate sampling modes, not different state spaces.
7. Uniform-\(\mathcal Q\) plus output-distance cost is the null control.
8. No existing Version 1 configuration may silently acquire Version 2 semantics.

## Issues

### V2-001 — Record the Version 1 baseline

Create `docs/archive/baselines/V1_BASELINE_FREEZE.md` containing:

- reviewed code revision or tag;
- accepted ADRs;
- representative configuration files;
- commands used to reproduce deterministic and pilot outputs;
- known provisional findings and limitations;
- list of artifacts that are not golden because they are stochastic, machine-dependent, or already known to be provisional.

Prefer a Git tag such as `v1-input-state-baseline` if the owner is ready to tag. Documentation must not assume the tag exists until it is created.

**Acceptance criteria**

- A developer can identify the exact baseline that Version 2 must preserve.
- At least two deterministic Version 1 fixtures have expected paths, costs, and expansion counts checked into tests or test data.
- Large Monte Carlo image files are not used as exact golden tests.

### V2-002 — Add ADR-014: Version 2 scope and state identity

Create `docs/software/architecture/adr/ADR-014-v2-output-state-on-invertible-branches.md`.

The ADR must state:

- context: biological motivation and the decision to remove wraparound from the core scope;
- decision: plain \(\mathcal Q\)-state search is allowed only on a certified injective branch;
- relationship to ADR-001: superseding only for Version 2 branch experiments, not globally replacing it;
- consequences: simpler task semantics, no duplicate preimage policy, loss of full-cycle topology from the core study;
- rejected alternatives:
  - merging duplicate preimages in \(\mathcal Q\);
  - planning in \((q,\sigma)\) now;
  - deleting Version 1;
  - retaining full-cycle behavior merely for software continuity.

**Acceptance criteria**

- The ADR gives a binary rule for choosing Version 1 or Version 2 state identity.
- It explicitly prohibits a plain \(\mathcal Q\) graph for a noninjective map.
- It defines the mathematical branch contract.

### V2-003 — Add ADR-015: topology, state embedding, and transition provenance

Create `docs/software/architecture/adr/ADR-015-topology-embedding-transition-provenance.md`.

The ADR must separate:

- node ID and adjacency;
- planning state \(\mathbf q\);
- actuator realization \(\mathbf u\);
- edge parameterization;
- sampling provenance.

It must define `INPUT_LINEAR` and `OUTPUT_LINEAR` transition parameterizations and explain why planning in \(\mathcal Q\) does not erase the actuator realization of an edge.

**Acceptance criteria**

- The ADR is sufficient to design a graph without referring to `PeriodicGrid2D`.
- It specifies which object owns each coordinate and transition operation.

### V2-004 — Add ADR-016: configuration and result compatibility

Create `docs/software/architecture/adr/ADR-016-v1-v2-configuration-compatibility.md`.

Decide:

- `architecture_version` is required for new Version 2 files;
- legacy Version 1 files remain accepted under their existing schema or explicit V1 loader;
- Version 2 results use a new schema version;
- loaders reject mixed fields such as `planning_space: output` with a Version 1 periodic graph configuration;
- run metadata records the architecture version.

**Acceptance criteria**

- No ambiguous YAML can be accepted.
- Compatibility behavior is testable before the Version 2 runner exists.

### V2-005 — Establish Version 1 golden fixtures

Add small deterministic fixtures covering:

1. unit gearbox, open grid, known start/goal;
2. four-bar or equivalent gearbox under the current Version 1 input-state graph;
3. Dijkstra/A* cost agreement;
4. expected node validity and connectivity;
5. serialization round trip for one Version 1 configuration.

Suggested location:

```text
tests/golden_v1/
├── test_search_golden.py
├── test_graph_golden.py
└── data/
    ├── fixture_unit_gearbox.json
    └── fixture_fourbar.json
```

Exact expansion order should be asserted only where deterministic tie-breaking and graph iteration are already guaranteed.

### V2-006 — Update Cursor rules

Update `.cursor/rules/project.mdc` so it no longer states unconditionally that all search identity lives in \(\mathcal U\).

Required rule:

- Version 1 noninjective/full-cycle experiments retain \(\mathcal U\)-state identity.
- Version 2 certified invertible-branch experiments use \(\mathcal Q\)-state identity with unique \(\mathcal U\) realization attached.
- Never collapse duplicate preimages.
- Read `architecture_version` and the relevant ADR before changing state semantics.

## Expected file changes

```text
docs/software/architecture/adr/ADR-014-v2-output-state-on-invertible-branches.md
docs/software/architecture/adr/ADR-015-topology-embedding-transition-provenance.md
docs/software/architecture/adr/ADR-016-v1-v2-configuration-compatibility.md
docs/archive/baselines/V1_BASELINE_FREEZE.md
.cursor/rules/project.mdc
tests/golden_v1/...
```

## Non-goals

- no generic graph implementation;
- no mechanism API changes;
- no new experiment runner;
- no branch inversion code;
- no large reruns;
- no moving existing source files.

## Recommended pull requests

1. **PR V2.0-A:** ADRs, project-plan links, and Cursor rule update.
2. **PR V2.0-B:** Version 1 baseline note and golden fixtures.

Keep documentation review separate from any later architectural implementation.

## Verification

```bash
pytest tests/golden_v1
pytest
ruff check .
ruff format --check .
mypy src
```

## Sprint exit criteria

Sprint V2.0 is complete when:

1. ADR-014, ADR-015, and ADR-016 are accepted;
2. the Cursor rule expresses conditional Version 1/Version 2 state identity;
3. at least two deterministic Version 1 golden fixtures pass;
4. the baseline revision and reproduction commands are recorded;
5. no production search or graph code has been rearchitected yet.

## Cursor starter prompt

```text
Implement Sprint V2.0 only. Read docs/software/PROJECT_PLAN.md, ADR-001, ADR-011,
and SPRINT_V2_0_CONTRACT_AND_BASELINE.md before editing. Preserve all Version 1
semantics. First inventory current configuration versioning, result schema,
Cursor rules, and deterministic tests. Then implement V2-001 through V2-006 in
small commits. Do not refactor search, graph, or mechanism code in this sprint.
Run targeted golden tests and the full CI commands after each issue. Record any
foundational disagreement as an ADR question rather than silently resolving it.
```
