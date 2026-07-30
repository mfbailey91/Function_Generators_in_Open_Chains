# ADR-015 — Topology, State Embedding, and Transition Provenance

**Status:** Accepted  
**Architecture versions:** Version 1 adapters and Version 2 graphs  
**Related:** ADR-001, ADR-011, ADR-014, ADR-016

## Context

Version 1 search reached through `ConstrainedInputGraph` into `PeriodicGrid2D`
indices and actuator coordinates. Version 2 needs dimension-independent
topology and must separate:

- which nodes are adjacent;
- which coordinates identify the planning state;
- which actuator values realize that state;
- how an edge is parameterized when tracing or costing it;
- how nodes were sampled.

Without that separation, output-state planning can accidentally erase actuator
realization or confuse sampling domain with state space.

## Decision

### Separable graph meanings

| Concern | Owner | Notes |
| --- | --- | --- |
| Node ID and adjacency | `GraphTopology` / concrete topology | Integer IDs; no physical coordinates |
| Planning state \(\mathbf q\) | Embedded planning graph | Version 2 identity (ADR-014) |
| Actuator realization \(\mathbf u\) | Embedded planning graph | Unique under certified branch |
| Edge parameterization | Transition provenance on the graph | Independent of planning identity |
| Sampling provenance | Sampling specification on the graph | Domain used to place nodes |

Version 1 continues to identify planning state with \(\mathbf u\); adapters may
expose the same topology contract without becoming Version 2 graphs.

### Topology contract

A topology object owns only discrete structure:

- `shape`, `node_count`;
- `node_id(index)` / `index_from_id(node_id)`;
- axis-aligned neighbors with optional per-axis wrap flags.

It does **not** own coordinate ranges, mechanism maps, or samples.
`PeriodicGrid2D` remains available for Version 1; `TensorGridTopology` is the
dimension-independent replacement for new code.

### Transition parameterizations

| Name | Parameterization | Typical sampling domain |
| --- | --- | --- |
| `INPUT_LINEAR` | Linear interpolate \(\mathbf u(s)\), then \(q=g(u)\) | Uniform \(\mathcal U\) |
| `OUTPUT_LINEAR` | Linear interpolate \(\mathbf q(s)\), then \(u=g^{-1}(q)\) | Uniform \(\mathcal Q\) |

Planning in \(\mathcal Q\) does **not** erase the actuator realization of an
edge. Edge traces and actuator-aware costs must recover \(\mathbf u(s)\) from
the declared parameterization and the certified branch.

### Sampling domains

`SamplingDomain.INPUT` and `SamplingDomain.OUTPUT` describe how lattice nodes
were placed. They are not alternate state spaces. Both Version 2 modes use
\(\mathcal Q\) as planning identity once the branch is certified.

## Consequences

Benefits:

- search can depend only on node IDs, validity, adjacency, and explicit costs;
- Version 2 graphs can share one uniform-\(\mathcal Q\) lattice across mechanisms;
- diagnostics and metrics can audit \(q\), \(u\), and transition provenance separately.

Costs:

- more explicit constructors and serialization fields;
- Version 1 code needs adapters during migration.

## Implementation consequences

- Minimal `SearchGraph` protocol excludes `q_state` / `u_state`.
- Concrete Version 2 graphs expose both coordinate accessors.
- Graph construction records sampling domain and transition parameterization.
