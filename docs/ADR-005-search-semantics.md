# ADR-005 — Search Expansion Semantics and Tie-Breaking

**Status:** Accepted

## Context

Version 1 reports node expansions as the primary planning metric. Dijkstra and
A* must share one counting convention so paired gearbox / four-bar trials are
comparable. Heap implementations that allow multiple entries per node must not
count stale pops as expansions. A* must return the same optimal cost as
Dijkstra when both use Version 1 output Euclidean edge weights.

Output coordinates live in the shared chart \(\mathcal Q\) (ADR-011). Raw
principal-angle subtraction is not a valid edge or heuristic metric.

## Decision

### Graph and cost

- Search runs on `ConstrainedInputGraph` (input-space nodes; ADR-001, ADR-004).
- Default edge weight is
  \(c(a,b)=d_{\mathcal Q}\bigl(g(u_a),g(u_b)\bigr)\)
  via `ConstrainedInputGraph.output_displacement` (IM-042; ADR-011 ownership).
  The graph-free helper `output_euclidean_cost` remains for unit tests without
  a graph instance.
- Start and goal are known valid flat node ids (selected preimages).

### Cost / heuristic compatibility (IM-035 / S4-02)

A* may use exactly one of:

1. the matching admissible output-space heuristic
   \(h(n)=d_{\mathcal Q}(q_n,q_{\mathrm{goal}})\) with Version 1 default costs;
2. a user-supplied heuristic documented for a custom cost, passed through
   `best_first_search`; or
3. a zero heuristic (Dijkstra / `zero_heuristic`).

`astar()` refuses a custom `edge_cost` paired with the default output
heuristic. Custom metrics must call `best_first_search` with an explicit
compatible heuristic, or use `dijkstra()`.

Sprint Four formalizes this as `PlanningObjective` via
`resolve_planning_objective(graph, goal, cost_name, heuristic_name=None)`:

| Edge cost | Default A* heuristic | Also allowed |
| --- | --- | --- |
| `uniform` | wrapped lattice Manhattan (`uniform_step`) | `zero` |
| `input_euclidean` | wrapped `d_U(u_n, u_goal)` | `zero` |
| `output_euclidean` | `d_Q(q_n, q_goal)` | `zero` |

Incompatible pairs raise `ValueError`. Experiment runners must resolve the
objective from configuration and record both `cost_type` and `heuristic_type`.

### Priority and tie-breaking

- Open-set key is `(f, node_id)` with \(f=g+h\).
- Dijkstra uses \(h\equiv 0\); default A* uses the output-space Euclidean
  heuristic above with \(q_{\mathrm{goal}}=\operatorname{canonicalize}(g(u_{\mathrm{goal}}))\).
- When `f` ties, the smaller flat `node_id` is expanded first (deterministic).

### Expansion and stale entries

A node is **expanded** when it is removed from the open heap at its
best-known `g` and its outgoing valid edges are examined.

A pop is **stale** (not an expansion) when:

1. its recorded `g` is strictly greater than the best-known `g` for that node,
   or
2. the node was already expanded (duplicate best-`g` heap entry).

Stale pops increment `n_stale` only.

`n_generated` counts open-heap pushes, including the start node.

### Optimality

With nonnegative edge weights, Dijkstra returns \(C^*\). The output-space
Euclidean heuristic is consistent for Version 1 edge costs (triangle
inequality in \(\mathcal Q\)), so A* returns the same \(C^*\). Project tests
assert cost equality on shared graphs.

### Reverse Dijkstra (exact cost-to-go)

Reverse Dijkstra grows from the goal using reverse edge weights
\(c(v,u)\) so that every reachable node \(n\) is labeled with exact
\(C^*(n,\mathrm{goal})\). Expansion and stale-entry counting match forward
Dijkstra. The resulting map validates heuristics: admissible \(h\) must
satisfy \(h(n)\le C^*(n,\mathrm{goal})\) on every labeled node, and
\(C^*(\mathrm{start},\mathrm{goal})\) must equal forward Dijkstra cost.

### Failure behavior

| Condition | Behavior |
| --- | --- |
| Start/goal out of range or invalid | `ValueError` |
| No path | `SearchResult(found=False, cost=inf, path=())` |
| Negative / non-finite edge or heuristic | `ValueError` |
| `astar(..., edge_cost=custom)` | `ValueError` (IM-035) |

## Consequences

Benefits:

- expansion counts are comparable across algorithms and mechanisms;
- A* cost can be validated against Dijkstra;
- tie-breaking removes nondeterministic path choice under equal `f`;
- custom metrics cannot silently reuse an unrelated heuristic.

Costs:

- multiple heap entries use more memory than decrease-key;
- finite-sample edge validation (ADR-004) remains a separate approximation.
