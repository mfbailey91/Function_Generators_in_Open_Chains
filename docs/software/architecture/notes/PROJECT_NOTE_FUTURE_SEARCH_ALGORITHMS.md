# Project Note — Sequenced Search-Algorithm Expansion

**Status:** Active sequencing note (V2.10 Dijkstra and V2.11 A* campaigns completed)
**Applies to:** Version 2 and later experiment architecture
**Current implementation priority:** Review paired Dijkstra/A* 2R evidence before bidirectional exact search
**Decision date:** 2026-08-04

**First implementation sprint:** [Sprint V2.10 — Production Monte Carlo Orchestration: Dijkstra Campaign](../../planning/sprints/v2/SPRINT_V2_10_PRODUCTION_MONTE_CARLO_ORCHESTRATION.md)  
**Second implementation sprint:** [Sprint V2.11 — A* Paired Campaign](../../planning/sprints/v2/SPRINT_V2_11_ASTAR_PAIRED_CAMPAIGN.md)

Issue slug: `production_monte_carlo_orchestration_v2_9` (filed before the U-distance diagnostic consumed the V2.9 number).

## Purpose

Preserve the long-term planner-comparison program without turning the first production Monte Carlo into a solver factorial.

The immediate research program evaluates **one graph solver at a time**. Dijkstra (V2.10) and A* (V2.11) now share the accepted mechanism population, task bank, graph semantics, objective, resolution, and result schema. Later search families must reuse that same frozen basis.

This sequence keeps the causal question legible:

> What planning effect is produced by the mechanism map under one completely specified search process?

Only after that result is stable should the project ask:

> How does a different search strategy interact with the same mechanism-induced graph geometry?

## Decision

### One solver per production campaign

A production configuration must select exactly one solver:

```yaml
search:
  algorithm: dijkstra
```

The production runner must reject solver lists such as:

```yaml
search:
  algorithms: [dijkstra, astar]
```

A solver comparison is created by running a later campaign against the same immutable sample bank, not by multiplying algorithms inside one Monte Carlo run.

### Campaign order

1. **Dijkstra** — explanatory reference and first production campaign.
2. **A\*** — informed optimal search on the same discrete graphs and paired sample bank.
3. **Bidirectional exact search** — considered after the one-directional exact solvers are understood.
4. **Sampling-based roadmaps** — PRM, Lazy PRM, and PRM* as a separate roadmap-construction study.
5. **Sampling-based trees** — RRT-Connect, RRT*, and later informed or batch planners if warranted.

This order is a research sequence, not a claim that Dijkstra is the most practical planner.

## Why Dijkstra comes first

Dijkstra exposes the weighted graph without a heuristic. Its expansion set is directly related to graph topology, edge costs, endpoint placement, and the induced cost basin. This makes it the cleanest first instrument for explaining how the transmission reshapes search.

The first production result should therefore establish:

- the distribution of paired mechanism effects under Dijkstra;
- the relationship between mechanism descriptors and Dijkstra search effort;
- the stability of the effect across mechanism and task variation;
- the sensitivity of the result to graph resolution;
- the distinction between search-effort changes and path-quality changes.

## A* campaign contract

A* is the second exact solver. [Sprint V2.11](../../planning/sprints/v2/SPRINT_V2_11_ASTAR_PAIRED_CAMPAIGN.md) executed that campaign; it was not part of the Dijkstra production sprint.

The A* campaign must reuse (and did reuse):

- the identical accepted mechanism-pair bank;
- the identical task bank and task IDs;
- the identical output bounds and graph resolution;
- the identical graph topology and edge objective;
- the identical exact-query overlays;
- the identical tie-breaking policy where applicable;
- the same exclusions and failure records.

Only the solver and heuristic may change.

The A* campaign must first prove:

1. heuristic admissibility for the configured objective;
2. Dijkstra/A* optimal-cost agreement on all regression fixtures;
3. deterministic results under fixed seeds and tie rules;
4. explicit recording of heuristic calls, reopened nodes, stale entries, and expansion savings.

The central paired quantity will be the change in mechanism effect between solvers, for example:

\[
\Delta_{A^*-D}
=
\log\!\left(
\frac{N_{\mathrm{expanded,FB},A^*}+1}
     {N_{\mathrm{expanded,GB},A^*}+1}
\right)
-
\log\!\left(
\frac{N_{\mathrm{expanded,FB},D}+1}
     {N_{\mathrm{expanded,GB},D}+1}
\right).
\]

This asks whether heuristic guidance suppresses, preserves, or reverses the mechanism effect observed under uninformed search.

## Bidirectional exact-search note

Bidirectional Dijkstra and bidirectional A* are future exact-search controls. They require additional contracts for:

- forward and reverse objective consistency;
- termination conditions;
- meeting-state semantics;
- multi-source and multi-goal endpoint sets;
- path reconstruction;
- expansion accounting across two frontiers.

They should not be added merely as faster implementations of the current solver. Their frontier geometry is itself a different search process and must be reported separately.

## Sampling-based planner note

Sampling-based planners change both the search process and the graph or tree construction process. They therefore belong to a separate experimental layer rather than the exact-grid Monte Carlo.

### Roadmap family

The first sampling-based study should favor multi-query roadmaps because the project already evaluates multiple tasks per mechanism:

- PRM;
- Lazy PRM;
- PRM*.

A roadmap study must distinguish:

- roadmap-construction cost;
- amortized query cost;
- samples drawn and accepted;
- edges proposed and validated;
- edge-validation calls;
- success probability;
- first-solution time;
- final path cost;
- memory use.

Node expansions alone are not a sufficient cross-family metric.

### Tree family

Later single-query planners may include:

- RRT-Connect for feasible-path discovery;
- RRT* for asymptotic path-quality convergence;
- informed or batch planners only after a specific research question justifies them.

### State and validity contract

Sampling-based planners must preserve the project’s accepted state semantics for the experiment version being run. They must use the same:

- state-space bounds;
- mechanism forward or inverse maps;
- periodic or nonperiodic axis semantics;
- output constraints;
- continuous edge validator;
- objective definition;
- endpoint task bank.

No sampling-based planner may collapse hidden mechanism state when the active mechanism map is noninjective.

## Architecture preparation without implementation

The Dijkstra sprint may make narrow, non-disruptive preparations:

```python
class GraphSolver(Protocol):
    @property
    def solver_id(self) -> str: ...

    def solve(
        self,
        graph: SearchGraph,
        start: int,
        goal: int,
        objective: EdgeObjective,
    ) -> SearchResult: ...
```

However, the sprint must not:

- add OMPL or another planning dependency;
- implement PRM or RRT;
- implement A* changes unrelated to Dijkstra compatibility;
- create a multi-solver production loop;
- broaden the production result schema beyond fields that remain meaningful for Dijkstra.

The architecture should permit later solvers without making the current sprint responsible for them.

## Result-package rule

Each immutable production package identifies exactly one solver:

```json
{
  "solver_id": "dijkstra",
  "solver_schema_version": 1,
  "heuristic_id": null
}
```

Later A* and sampling-based packages receive separate run IDs and may be joined analytically through shared mechanism IDs, task IDs, graph IDs, and sample-bank versions.

## Non-goals

- No solver leaderboard in the Dijkstra production sprint.
- No claim that expansion counts are directly comparable across all planner families.
- No selection of the “best” planner before the mechanism effect is understood.
- No changing the mechanism population between solver campaigns without preserving the original paired bank.
- No simultaneous solver execution inside one production worker.

## Promotion criteria for the next solver

A* becomes the next active solver only after the Dijkstra campaign has:

1. produced a resumable and immutable production run;
2. passed resolution and graph-invariant checks;
3. completed the minimum accepted mechanism count;
4. generated hierarchical uncertainty estimates;
5. documented exclusions and failures;
6. frozen the sample bank for paired reuse;
7. produced a reviewed report that identifies which Dijkstra findings A* is meant to test.
