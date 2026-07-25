"""A* search with output-space Euclidean heuristic.

Uses the same expansion and stale-entry semantics as Dijkstra (ADR-005).
Tie-breaking is deterministic: ascending flat ``node_id`` when ``f`` ties.
"""

from __future__ import annotations

from collections.abc import Callable

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.core import _cached_outputs, best_first_search
from inequality_mechanisms.search.heuristics import output_euclidean_heuristic
from inequality_mechanisms.search.result import SearchResult


def astar(
    graph: ConstrainedInputGraph,
    start: int,
    goal: int,
    *,
    edge_cost: Callable[[int, int], float] | None = None,
) -> SearchResult:
    """Compute an optimal path with ``f = g + ||q_n - q_goal||_2``.

    The goal output ``q_goal = g(u_goal)`` is taken from the goal node so
    ``h(goal) = 0``. With Version 1 output Euclidean edge costs the heuristic
    is consistent, so the first expansion of the goal yields ``C*``.

    Parameters
    ----------
    graph :
        Constrained input lattice.
    start, goal :
        Flat valid node ids (known preimages in Version 1 trials).
    edge_cost :
        Optional edge-weight override; default is output Euclidean cost.

    Returns
    -------
    SearchResult
        Optimal path and instrumentation counters.
    """
    output_of = _cached_outputs(graph)
    q_goal = output_of(goal)
    heuristic = output_euclidean_heuristic(graph.mechanism, q_goal, output_of)
    return best_first_search(
        graph,
        start,
        goal,
        heuristic,
        edge_cost=edge_cost,
    )
