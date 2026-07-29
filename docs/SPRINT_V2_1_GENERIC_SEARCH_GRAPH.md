# Sprint V2.1 — Generic Search Graph and Topology Boundary

## Theme

> Refactor the engine before changing the experiment.

## Objective

Remove Dijkstra and A* dependencies on `ConstrainedInputGraph`, `PeriodicGrid2D`, two-dimensional indices, and actuator coordinates while reproducing Version 1 behavior exactly through adapters.

This sprint changes software architecture but must not change scientific semantics or Version 1 results.

## Current coupling to remove

The current best-first search implementation reaches through the graph into:

- `graph.grid.node_count`;
- `grid.indices_from_id()`;
- `graph.neighbors(i0, i1)`;
- `grid.node_id()`;
- default output costs built from input-grid coordinates.

The new search core must see only node IDs, validity, adjacency, an objective, and a heuristic.

## Target contracts

### Search graph

Create `src/inequality_mechanisms/search/protocol.py`:

```python
from collections.abc import Iterable
from typing import Protocol

class SearchGraph(Protocol):
    @property
    def node_count(self) -> int: ...

    def node_is_valid(self, node_id: int) -> bool: ...

    def neighbors(self, node_id: int) -> Iterable[int]: ...
```

Do not include mechanism, coordinate, or grid methods in the minimal search protocol.

### Planning objective

Search receives an explicit edge-cost callable. No graph-type-specific default belongs in `best_first_search` after this sprint.

```python
EdgeCost = Callable[[int, int], float]
Heuristic = Callable[[int], float]
```

A higher-level objective resolver may provide defaults for Version 1, but the search core must not construct them.

### Topology contract

Create `src/inequality_mechanisms/graphs/topology.py`:

```python
class GraphTopology(Protocol):
    @property
    def shape(self) -> tuple[int, ...]: ...

    @property
    def node_count(self) -> int: ...

    def node_id(self, index: tuple[int, ...]) -> int: ...
    def index_from_id(self, node_id: int) -> tuple[int, ...]: ...
    def neighbors(self, node_id: int) -> Iterable[int]: ...
```

Implement `TensorGridTopology` with:

- arbitrary dimension \(D\ge1\);
- deterministic row-major node IDs;
- axis-aligned \(2D\)-connectivity;
- per-axis wrap flags;
- no physical coordinates.

`PeriodicGrid2D` remains available for Version 1. A compatibility adapter or internal delegation may be introduced, but do not rewrite it unless required by tests.

## Issues

### V2-101 — Inventory search and graph coupling

Before code changes, record direct dependencies on:

- `ConstrainedInputGraph` in `search/`;
- `.grid` access in search, heuristics, reverse search, metrics, and diagnostics;
- two-index neighbor APIs;
- implicit default edge-cost behavior.

Deliver `docs/notes/V2_1_SEARCH_COUPLING_AUDIT.md` with before/after status.

### V2-102 — Add `SearchGraph` protocol

Implement the minimal protocol and type all search entry points against it.

Requirements:

- node IDs remain `int`;
- invalid start/goal behavior remains unchanged;
- neighbor iteration order remains deterministic;
- protocol does not require coordinates.

### V2-103 — Make edge cost explicit

Change `best_first_search` so `edge_cost` is required, or provide a thin Version 1 wrapper that resolves the legacy default before calling a fully explicit core.

Preferred structure:

```python
def best_first_search(
    graph: SearchGraph,
    start: int,
    goal: int,
    *,
    edge_cost: EdgeCost,
    heuristic: Heuristic,
    record_expanded: bool = False,
) -> SearchResult:
    ...
```

Compatibility wrapper:

```python
def search_v1(...):
    objective = resolve_v1_objective(...)
    return best_first_search(...)
```

Do not preserve an implicit graph-specific default inside the generic core.

### V2-104 — Adapt `ConstrainedInputGraph`

Add node-ID-based methods without removing existing index-based APIs:

```python
@property
def node_count(self) -> int: ...

def node_is_valid(self, node_id: int) -> bool: ...

def neighbors_by_id(self, node_id: int) -> tuple[int, ...]: ...
```

Use an adapter if naming conflicts would create churn:

```python
class ConstrainedInputSearchAdapter(SearchGraph):
    ...
```

The adapter must preserve current neighbor ordering and expansion semantics.

### V2-105 — Add `TensorGridTopology`

Implement and test 1D, 2D, and 3D shapes.

Required tests:

- deterministic row-major ID conversion;
- boundary neighbors without wrap;
- wrapped neighbors per axis;
- no duplicate neighbors on size-2 wrapped axes;
- deterministic edge iteration;
- invalid shape and ID errors.

### V2-106 — Migrate reverse search and heuristics

Any reverse-distance or exact cost-to-go implementation must use the generic graph protocol and explicit edge costs.

Heuristics may close over a concrete graph's coordinate APIs, but the search core must not know which coordinates they use.

### V2-107 — Prove Version 1 equivalence

Run golden fixtures before and after the refactor.

Assert:

- found/not-found status;
- optimal cost;
- reconstructed path;
- expanded count;
- generated count;
- stale count;
- expanded order where already deterministic.

## Expected file changes

```text
src/inequality_mechanisms/search/protocol.py
src/inequality_mechanisms/search/core.py
src/inequality_mechanisms/graphs/topology.py
src/inequality_mechanisms/graphs/adapters.py       # optional
src/inequality_mechanisms/graphs/validation.py     # additive compatibility methods
tests/search/...
tests/graphs/test_tensor_topology.py
tests/golden_v1/...
docs/notes/V2_1_SEARCH_COUPLING_AUDIT.md
```

## Design constraints

- Keep `SearchGraph` minimal.
- Do not put `q_state()` or `u_state()` in the minimal search protocol.
- Do not let `TensorGridTopology` own coordinate ranges or samples.
- Do not introduce NetworkX into production search.
- Do not change tie-breaking.
- Do not optimize memory until correctness is demonstrated.
- Do not implement Version 2 graphs in this sprint.

## Recommended pull requests

1. **PR V2.1-A:** coupling audit and `SearchGraph` protocol.
2. **PR V2.1-B:** explicit search objective and Version 1 adapter.
3. **PR V2.1-C:** `TensorGridTopology` and tests.
4. **PR V2.1-D:** reverse-search migration and golden equivalence closeout.

## Verification

```bash
pytest tests/search tests/graphs tests/golden_v1
pytest
ruff check .
ruff format --check .
mypy src
```

## Sprint exit criteria

1. `search/core.py` does not import `ConstrainedInputGraph` or `PeriodicGrid2D`.
2. Search iterates neighbor node IDs directly.
3. Edge cost is explicit at the generic search boundary.
4. `TensorGridTopology` passes 1D/2D/3D tests.
5. All Version 1 golden results are unchanged.
6. No Version 2 scientific behavior has been introduced yet.

## Cursor starter prompt

```text
Implement Sprint V2.1 only. Begin with V2-101 and write the coupling audit before
refactoring. Introduce the smallest SearchGraph protocol possible, make edge
cost explicit, and adapt the existing ConstrainedInputGraph without changing
Version 1 results. Add TensorGridTopology as a coordinate-free N-dimensional
topology. Preserve tie-breaking, neighbor order, and search instrumentation.
After each issue run targeted tests; after each PR slice run all golden Version 1
tests and full CI. Do not implement operating branches or output-state graphs.
```
