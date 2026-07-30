# V2.1 — Search / `ConstrainedInputGraph` coupling audit

Sprint V2.1 (V2-101) inventory of direct dependencies from `search/` on
`ConstrainedInputGraph`, `PeriodicGrid2D`, two-index neighbor APIs, and the
implicit default edge cost, taken before the refactor. See
`docs/software/planning/sprints/v2/SPRINT_V2_1_GENERIC_SEARCH_GRAPH.md` for
the sprint objective and exit criteria.

## Classification key

| Class | Meaning |
| --- | --- |
| **generic-core coupling (removed)** | Reached through the graph from inside `search/core.py`; must not remain after this sprint |
| **V1 public API (kept)** | Public Version 1 function signature naming `ConstrainedInputGraph`; preserved for callers |
| **V1 compatibility helper (kept, moved)** | Version 1 only logic, relocated out of `search/core.py` |
| **adapter (new)** | New code translating a V1 graph into the generic `SearchGraph` shape |

## Before (direct couplings removed from the generic core)

| Location | Coupling | Class |
| --- | --- | --- |
| `search/core.py::best_first_search` | `graph: ConstrainedInputGraph` parameter type | generic-core coupling (removed) |
| `search/core.py::best_first_search` | `graph.grid.node_count` for the start/goal range check | generic-core coupling (removed) |
| `search/core.py::best_first_search` | `graph.node_is_valid_id(start / goal)` | generic-core coupling (removed) |
| `search/core.py::best_first_search` | implicit default edge cost built from `graph.grid.indices_from_id`, `graph.grid.coordinates`, `graph.output_displacement` when `edge_cost is None` | generic-core coupling (removed) |
| `search/core.py::best_first_search` | `graph.grid.indices_from_id(u)` to get `(i0, i1)` before expanding | generic-core coupling (removed) |
| `search/core.py::best_first_search` | `graph.neighbors(i0, i1)` (two-index neighbor API) | generic-core coupling (removed) |
| `search/core.py::best_first_search` | `graph.grid.node_id(j0, j1)` to re-flatten each neighbor | generic-core coupling (removed) |
| `search/core.py::_cached_outputs` | `graph.grid.coordinates`, `graph.grid.indices_from_id`, `graph.output` | V1 compatibility helper (kept, moved) |
| `search/cost_to_go.py::reverse_dijkstra` | `graph: ConstrainedInputGraph` parameter type, `graph.grid.node_count`, `graph.node_is_valid_id`, `graph.grid.indices_from_id`, `graph.neighbors(i0, i1)`, `graph.grid.node_id(j0, j1)`, implicit default edge cost | generic-core coupling (removed) / V1 public API (kept) |
| `search/dijkstra.py::dijkstra` | `graph: ConstrainedInputGraph` parameter type; passed straight through to `best_first_search` | V1 public API (kept) |
| `search/astar.py::astar` | `graph: ConstrainedInputGraph` parameter type; `_cached_outputs(graph)` imported from `search.core`; passed straight through to `best_first_search` | V1 public API (kept) |
| `search/heuristics.py::uniform_step_heuristic`, `input_euclidean_heuristic` | `graph.grid.indices_from_id`, `graph.grid.shape`, `graph.grid.wrap`, `graph.grid.coordinates` | out of scope (heuristics may close over concrete coordinate APIs per sprint design constraints) |
| `search/objectives.py::_build_heuristic` | `_cached_outputs` imported from `search.core`; `graph.mechanism`, `graph.output_space` passed to heuristics | V1 compatibility helper (kept, moved) |
| `graphs/costs.py::output_euclidean_edge_cost`, `input_euclidean_cost` | `graph.grid.coordinates`, `graph.grid.indices_from_id`, `graph.output_displacement`, `graph.grid.wrap` | out of scope (graph-owned cost builders; not `search/core.py`) |

Two-index neighbor coupling was the dominant pattern: every traversal step in
`best_first_search` and `reverse_dijkstra` round-tripped a flat node id
through `grid.indices_from_id` → `graph.neighbors(i0, i1)` → `grid.node_id`,
which is exactly the `ConstrainedInputGraph` / `PeriodicGrid2D` two-index
shape the sprint targets for removal from the generic core.

Implicit default edge cost was built inline in both `best_first_search` and
`reverse_dijkstra` whenever `edge_cost is None`, duplicating the same
Version 1 output-Euclidean formula already available as
`graphs.costs.output_euclidean_edge_cost`.

## After (post-refactor status)

| Location | Status |
| --- | --- |
| `search/protocol.py` | **New.** Minimal `SearchGraph` Protocol (`node_count`, `node_is_valid(node_id)`, `neighbors(node_id)`), plus `EdgeCost` and `Heuristic` aliases. No coordinate, mechanism, or grid methods. |
| `search/core.py::best_first_search` | Refactored. Type is `graph: SearchGraph`; `edge_cost` and `heuristic` are required keyword-only arguments. Uses only `graph.node_count`, `graph.node_is_valid(node_id)`, `graph.neighbors(node_id)`. **Imports neither `ConstrainedInputGraph` nor `PeriodicGrid2D`.** |
| `search/core.py::_cached_outputs` | **Removed** from this module (moved to `search/v1_compat.py`). |
| `search/v1_compat.py` | **New.** Holds `_cached_outputs` (moved, unchanged body) and the new `resolve_v1_default_edge_cost(graph) -> EdgeCost` helper, which delegates to `graphs.costs.output_euclidean_edge_cost`. This is the only module that reconstructs the pre-refactor implicit default. |
| `graphs/validation.py::ConstrainedInputGraph.node_count` | **New, additive.** `@property` forwarding `grid.node_count`. Does not touch the existing `node_is_valid(i0, i1)` two-index method. |
| `graphs/validation.py::ConstrainedInputGraph.neighbors_by_id` | **New, additive.** Flat-id neighbor query; order matches `neighbors(i0, i1)` composed with `grid.node_id`. Existing two-index `neighbors(i0, i1)` and `node_is_valid(i0, i1)` / `node_is_valid_id(node_id)` are unchanged. |
| `graphs/adapters.py::ConstrainedInputSearchAdapter` | **New.** Implements `SearchGraph` for `ConstrainedInputGraph` (or any object matching the same `.grid` / `neighbors(i0, i1)` / `node_is_valid_id` duck type, e.g. `MonotonicOutputGraph`). `neighbors()` performs the same `indices_from_id → neighbors(i0, i1) → node_id` translation that used to live inline in `search/core.py`, so neighbor order and therefore tie-breaking are unchanged. |
| `search/dijkstra.py::dijkstra` | Public V1 signature unchanged (`graph: ConstrainedInputGraph`). Internally resolves `resolve_v1_default_edge_cost(graph)` when `edge_cost is None`, wraps `graph` in `ConstrainedInputSearchAdapter`, and calls `best_first_search(..., edge_cost=..., heuristic=zero_heuristic, ...)`. |
| `search/astar.py::astar` | Public V1 signature unchanged. Imports `_cached_outputs` and `resolve_v1_default_edge_cost` from `search.v1_compat` (no longer from `search.core`). Wraps `graph` in `ConstrainedInputSearchAdapter` before calling `best_first_search`. |
| `search/cost_to_go.py::reverse_dijkstra` | Public V1 signature unchanged. Resolves the default edge cost via `resolve_v1_default_edge_cost`, wraps `graph` in `ConstrainedInputSearchAdapter`, and delegates to a new generic `_reverse_dijkstra_generic(graph: SearchGraph, goal, *, edge_cost: EdgeCost)` that uses only `graph.node_count`, `graph.node_is_valid`, `graph.neighbors`. |
| `search/objectives.py` | Imports `_cached_outputs` from `search.v1_compat` instead of `search.core`. `resolve_planning_objective` and heuristic construction are otherwise unchanged. |
| `search/heuristics.py::Heuristic` | Re-exported from `search.protocol` (single canonical definition) instead of a duplicate local `Callable[[int], float]` alias. |
| `search/__init__.py` | Exports `SearchGraph`, `EdgeCost`, `Heuristic`, and `best_first_search` in addition to existing public names. |
| `experiments/pilot.py::_run_search` | Updated call site: wraps `graph` in `ConstrainedInputSearchAdapter` and passes `heuristic=` as a keyword argument (was positional) to match the new `best_first_search` signature. |
| `graphs/topology.py` (`GraphTopology`, `TensorGridTopology`) | Present in the working tree from parallel V2-105 work; out of scope for this audit and untouched by it. |

### Unresolved / explicitly out of scope

- `search/heuristics.py::uniform_step_heuristic` and `input_euclidean_heuristic` still close over `graph.grid` (coordinates, shape, wrap). This is permitted by the sprint design constraints ("heuristics may close over a concrete graph's coordinate APIs, but the search core must not know which coordinates they use") and is unchanged by this sprint.
- `graphs/costs.py` edge-cost builders (`output_euclidean_edge_cost`, `input_euclidean_cost`, `uniform_edge_cost`) still take a `ConstrainedInputGraph`. They are graph-owned cost constructors, not part of `search/core.py`, and are exactly what Version 1 callers use to build the `EdgeCost` they now must pass explicitly.
- `MonotonicOutputGraph` (`graphs/output_grid.py`) is not `ConstrainedInputGraph` but is passed to `dijkstra` / `astar` at several call sites (`experiments/sprint4_qgrid.py`, `tests/graphs/test_output_grid.py`) via the same two-index duck type. `ConstrainedInputSearchAdapter` is written against that duck type (not against `ConstrainedInputGraph.neighbors_by_id` specifically) so both graph types keep working unchanged.

## Verification

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/search tests/golden_v1 -q
MPLBACKEND=Agg PYTHONPATH=src .venv/bin/python -m pytest -q
```

Both the targeted Version 1 search/golden suites and the full project test
suite pass unchanged after the refactor (see sprint issue V2-107).

## Exit criteria status (Sprint V2.1)

1. `search/core.py` does not import `ConstrainedInputGraph` or `PeriodicGrid2D`. — **Met.**
2. Search iterates neighbor node IDs directly (`graph.neighbors(u)` yields ints). — **Met.**
3. Edge cost is explicit (required keyword-only) at the generic search boundary. — **Met.**
4. All Version 1 golden results are unchanged (`tests/golden_v1` passes byte-for-byte on cost, path, and instrumentation counters). — **Met.**
5. No Version 2 scientific behavior (`OperatingBranch`, Version 2 graphs) introduced by this change. — **Met** (this sprint slice only touches search decoupling and the `ConstrainedInputGraph` adapter; `TensorGridTopology` in `graphs/topology.py` is separate, unrelated work already present in the tree).
