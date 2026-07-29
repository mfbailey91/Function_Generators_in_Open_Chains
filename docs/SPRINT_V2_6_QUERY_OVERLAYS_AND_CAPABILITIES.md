# Sprint V2.6 — Exact Query Overlays and Initial Capability Objectives

## Theme

> Remove endpoint discretization as a confound, then let the mechanism matter for physically meaningful reasons.

## Objective

Add exact start/goal query nodes to sampled graphs and introduce the first mechanism-aware objectives that operate on a common output-state graph without relying solely on nonuniform node placement.

## Part A — Exact query overlays

### Problem

A requested continuous state \(\mathbf q_*\) will not generally be a sampled node, especially on the actuator-sampled nonuniform graph. Nearest-node snapping can change task distance and mechanism comparisons.

### Overlay model

Create a lightweight graph wrapper that adds query nodes without mutating the base graph:

```python
@dataclass(frozen=True)
class QueryNode:
    node_id: int
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    neighbors: tuple[int, ...]

class QueryOverlayGraph(SearchGraph):
    base: EmbeddedPlanningGraph
    query_nodes: tuple[QueryNode, ...]
```

The query state must satisfy:

\[
\mathbf u_*=g^{-1}(\mathbf q_*).
\]

Connect it only to physically neighboring lattice nodes. Validate every inserted edge with the base graph's transition model.

## Issues

### V2-601 — Define query-node connectivity

For a tensor-product lattice, locate the enclosing cell in the sampling domain and propose the cell's corner nodes as candidates.

Requirements:

- deterministic candidate ordering;
- no connection across a branch boundary;
- no periodic wrapping;
- no connection to invalid nodes;
- edge traces validate all accepted connections;
- start and goal overlays may coexist;
- exact sampled state reuses the existing node instead of duplicating it.

### V2-602 — Implement overlay-aware search and metrics

Search already consumes node IDs and adjacency. Ensure objectives, heuristics, path metrics, visualization, and serialization resolve both base and overlay states.

No special cases should be added to the generic search algorithm.

### V2-603 — Replace snapping in primary controlled configs

Retain nearest-node matching as a diagnostic mode, but use exact overlays for the primary study.

Report comparisons showing how much prior results changed when snapping was removed.

## Part B — Initial capability objectives

### Design principle

Capability objectives must be explicit, nonnegative, dimensionally documented, and paired with a safe heuristic. Use zero heuristic until an admissible one is proven.

### V2-604 — Actuator-travel objective on common \(\mathcal Q\) graphs

Use edge trace or endpoint actuator displacement:

\[
c_U(a,b)=\|\mathbf u_b-\mathbf u_a\|_2.
\]

For nonlinear edges, optionally compare endpoint displacement with integrated actuator arc length. Document which definition is used.

### V2-605 — Resolution or gain-exposure objective

Prototype a cost based on local transmission gain. One acceptable form is:

\[
c_{\mathrm{gain}}(a,b)
=
\int_0^1
\phi\!\left(J_g(\mathbf u(s))\right)
\left\|\frac{d\mathbf q}{ds}\right\|ds,
\]

where \(\phi\) is explicitly selected and normalized.

Possible initial \(\phi\):

- penalty for coarse output resolution, proportional to \(|dq/du|\);
- penalty for proximity to low-authority regions;
- task-specific preference for high or low gain.

Do not call this energy or torque cost unless those physical quantities are actually modeled.

### V2-606 — Terminal capability objective

Support a terminal-state term separate from edge cost, such as preference for fine output resolution at the goal:

\[
J(\pi)=\sum_{e\in\pi}c(e)+w_T\Phi(\mathbf q_{\mathrm{goal}}).
\]

Because a fixed single goal makes a terminal term constant, use this only with a goal set or region. Otherwise defer it to the 3R redundant-goal sprint.

### V2-607 — Objective registry and dimensional metadata

Every objective stores:

- name;
- mathematical definition;
- units or declared dimensionless normalization;
- parameters and weights;
- integration sample count;
- compatible heuristic;
- whether it depends on transition provenance.

### V2-608 — Controlled comparison

On the same uniform-\(\mathcal Q\) graph, compare matched gearbox and four-bar branches under:

- output distance;
- actuator travel;
- one carefully defined gain/resolution objective.

This isolates metric/capability effects from sampling effects.

## Tests

- exact query state round trip;
- overlay connection inside a cell;
- boundary query;
- exact sampled query deduplication;
- rejected outside-branch query;
- path through overlay matches analytic simple fixture;
- Dijkstra/A* agreement with zero heuristic;
- objective nonnegativity and finite values;
- integration convergence on affine fixtures;
- no change to base graph arrays;
- Version 1 and earlier Version 2 regressions.

## Non-goals

- no true dynamics or power model;
- no torque-limit feasibility;
- no reinforcement learning;
- no obstacles;
- no 3R implementation in this sprint;
- no unvalidated composite score containing many arbitrary weights.

## Sprint exit criteria

1. Exact output start/goal states can be inserted without mutating base graphs.
2. Primary controlled tasks no longer depend on endpoint snapping.
3. Output and actuator objectives run on the same uniform-\(\mathcal Q\) graph.
4. At least one gain/resolution objective has a documented mathematical and dimensional interpretation.
5. Dijkstra remains the reference for objectives without a proven heuristic.
6. The report states which effects remain after both sampling and endpoint discretization are controlled.

## Cursor starter prompt

```text
Implement Sprint V2.6 only. Add a QueryOverlayGraph wrapper with exact Q query
states, unique U realizations, deterministic local connectivity, and edge-trace
validation. Do not modify generic search for overlays. Replace snapping only in
new primary Version 2 configs and preserve snapping as a diagnostic. Then add
explicit actuator-travel and one narrowly defined gain/resolution objective with
zero heuristic unless admissibility is proven. Document units and parameters.
Do not implement dynamics, obstacles, or 3R work.
```
