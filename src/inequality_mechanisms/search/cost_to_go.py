"""Exact cost-to-go maps from reverse Dijkstra.

Reverse Dijkstra grows from the goal using reverse edge weights so that
``costs[n]`` is the optimal path cost from ``n`` to the goal. Version 1
output Euclidean costs are symmetric, so reverse weights equal forward
weights on the undirected lattice; the reverse formulation remains correct
if asymmetric costs are introduced later.

Used to validate admissible heuristics: ``h(n) <= costs[n]`` for every
reachable node (ADR-005).
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from inequality_mechanisms.graphs.costs import output_euclidean_cost
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.heuristics import Heuristic


@dataclass(frozen=True, slots=True)
class CostToGoMap:
    """Exact optimal cost from each reachable node to a fixed goal.

    Attributes
    ----------
    goal :
        Flat goal node id used as the reverse-search source.
    costs :
        Mapping ``node_id -> C*(node, goal)``. Nodes absent from the map
        (or queried via ``__getitem__``) are treated as unreachable
        (``inf``).
    n_expanded :
        Nodes expanded under ADR-005 semantics (stale pops excluded).
    n_generated :
        Open-heap pushes including the goal.
    n_stale :
        Discarded stale heap pops.
    """

    goal: int
    costs: Mapping[int, float]
    n_expanded: int
    n_generated: int
    n_stale: int

    def __getitem__(self, node_id: int) -> float:
        """Return exact cost-to-go, or ``inf`` if unreachable."""
        return float(self.costs.get(node_id, math.inf))

    def as_heuristic(self) -> Heuristic:
        """Return ``h(n) = C*(n, goal)`` (exact, possibly ``inf``)."""

        def h(node_id: int) -> float:
            return self[node_id]

        return h


def reverse_dijkstra(
    graph: ConstrainedInputGraph,
    goal: int,
    *,
    edge_cost: Callable[[int, int], float] | None = None,
) -> CostToGoMap:
    """Compute exact cost-to-go to ``goal`` for every reachable node.

    The open-set key is ``(g, node_id)`` with the same stale-entry and
    expansion counting rules as forward Dijkstra (ADR-005). Search does not
    stop early: the entire goal-reachable component is labeled.

    When expanding node ``u`` toward a neighbor ``v``, the reverse edge
    weight ``edge_cost(v, u)`` is used so that path costs match forward
    ``v → … → goal`` orientation.

    Parameters
    ----------
    graph :
        Constrained input lattice.
    goal :
        Flat valid node id (reverse-search source).
    edge_cost :
        Optional ``(u_id, v_id) -> float`` forward edge weight. Defaults to
        Version 1 output Euclidean cost. Reverse search queries
        ``edge_cost(v, u)``.

    Returns
    -------
    CostToGoMap
        Exact costs and instrumentation counters.

    Raises
    ------
    ValueError
        If ``goal`` is out of range or not a valid node, or if an edge cost
        is negative / non-finite.
    """
    n_nodes = graph.grid.node_count
    if goal < 0 or goal >= n_nodes:
        raise ValueError(f"goal node_id out of range: {goal}")
    if not graph.node_is_valid_id(goal):
        raise ValueError(f"goal node {goal} is not valid under graph constraints")

    cost_fn = edge_cost
    if cost_fn is None:
        mech = graph.mechanism
        grid = graph.grid

        def cost_fn(u_id: int, v_id: int) -> float:
            u = grid.indices_from_id(u_id)
            v = grid.indices_from_id(v_id)
            return output_euclidean_cost(
                mech,
                grid.coordinates(*u),
                grid.coordinates(*v),
            )

    g_best: dict[int, float] = {goal: 0.0}
    # Heap entries: (g, node_id). Tie-break on node_id only.
    open_heap: list[tuple[float, int]] = []
    heapq.heappush(open_heap, (0.0, goal))
    n_generated = 1
    n_expanded = 0
    n_stale = 0
    closed: set[int] = set()

    while open_heap:
        g_u, u = heapq.heappop(open_heap)
        best = g_best.get(u, math.inf)
        if g_u > best:
            n_stale += 1
            continue
        if u in closed:
            n_stale += 1
            continue

        n_expanded += 1
        closed.add(u)

        i0, i1 = graph.grid.indices_from_id(u)
        for j0, j1 in graph.neighbors(i0, i1):
            v = graph.grid.node_id(j0, j1)
            if v in closed:
                continue
            # Reverse edge: forward path is v → u → … → goal.
            tentative = g_u + cost_fn(v, u)
            if not math.isfinite(tentative) or tentative < 0.0:
                raise ValueError(
                    f"reverse edge cost from {v} to {u} produced non-finite or "
                    f"negative path cost {tentative}"
                )
            prev = g_best.get(v, math.inf)
            if tentative < prev:
                g_best[v] = tentative
                heapq.heappush(open_heap, (tentative, v))
                n_generated += 1

    return CostToGoMap(
        goal=goal,
        costs=dict(g_best),
        n_expanded=n_expanded,
        n_generated=n_generated,
        n_stale=n_stale,
    )
