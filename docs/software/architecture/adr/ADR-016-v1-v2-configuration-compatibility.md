# ADR-016 — Version 1 / Version 2 Configuration and Result Compatibility

**Status:** Accepted  
**Architecture versions:** Version 1 and Version 2  
**Related:** ADR-006, ADR-007, ADR-014, ADR-015

## Context

Version 1 configs (ADR-006) omit `architecture_version` and use periodic
input-state graphs, preimage policies, and Version 1 result schemas. Version 2
introduces output-state planning, certified branches, and separate sampling
modes. Ambiguous YAML that mixes those fields would silently corrupt science.

## Decision

### Architecture version

| File class | Rule |
| --- | --- |
| Legacy Version 1 configs | Accepted under the existing ADR-006 schema / V1 loader. Missing `architecture_version` means Version 1. |
| New Version 2 configs | Require `architecture_version: 2`. |
| Results | Version 2 results use a distinct `result_schema_version` (integer or string series separate from V1 sprint schemas). |
| Run metadata | Must record architecture version and result schema version. |

### Rejection of mixed semantics

Loaders must reject combinations such as:

- `planning_space: output` with a Version 1 periodic full-cycle graph config;
- Version 2 branch fields on a Version 1 config without `architecture_version: 2`;
- `architecture_version: 2` with Version 1-only `preimage_policy` task semantics;
- wrapped Version 2 branch topology;
- `planning_space` other than `output` for Version 2.

Version 1 reproduction commands must not route through the Version 2 runner.

### Compatibility testing before the Version 2 runner

A shared architecture-version gate (pure validation of raw mapping fields) must
be testable before the full Version 2 experiment runner exists. It classifies a
config mapping as Version 1 or Version 2 and raises on mixed fields.

## Consequences

Benefits:

- no ambiguous YAML;
- Version 1 baselines remain runnable;
- Version 2 results cannot be mistaken for Version 1 rows.

Costs:

- duplicate loader paths during coexistence;
- stricter authoring of Version 2 configs.

## Implementation consequences

- `inequality_mechanisms.experiments.architecture.classify_architecture_version`
  (or equivalent) rejects mixed fields.
- Version 2 typed config models live beside Version 1 pydantic models.
- Golden Version 1 fixtures continue to load without `architecture_version`.
