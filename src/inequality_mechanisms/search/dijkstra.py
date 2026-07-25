"""Dijkstra search on constrained input graphs.

Equivalent to best-first search with ``h ≡ 0``. Expansion semantics match A*
(ADR-005): stale heap entries are discarded without counting as expansions.
"""

from __future__ import annotations

from collections.abc import Callable

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.heuristics import zero_heuristic
from inequality_mechanisms.search.result import SearchResult


def dijkstra(
    graph: ConstrainedInputGraph,
    start: int,
    goal: int,
    *,
    edge_cost: Callable[[int, int], float] | None = None,
) -> SearchResult:
    """Compute an optimal path by accumulated edge cost only.

    Parameters
    ----------
    graph :
        Constrained input lattice.
    start, goal :
        Flat valid node ids.
    edge_cost :
        Optional edge-weight override; default is output Euclidean cost.

    Returns
    -------
    SearchResult
        Optimal path and instrumentation counters.
    """
    return best_first_search(
        graph,
        start,
        goal,
        zero_heuristic,
        edge_cost=edge_cost,
    )
