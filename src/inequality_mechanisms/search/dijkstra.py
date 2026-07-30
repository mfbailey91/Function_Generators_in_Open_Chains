"""Dijkstra search on constrained input graphs.

Equivalent to best-first search with ``h ≡ 0``. Expansion semantics match A*
(ADR-005): stale heap entries are discarded without counting as expansions.

Sprint V2.1: the generic core (``search/core.py``) no longer knows about
``ConstrainedInputGraph``. This module resolves the Version 1 default edge
cost and wraps the graph in ``ConstrainedInputSearchAdapter`` before calling
``best_first_search``, preserving the public V1 signature and behavior.
"""

from __future__ import annotations

from collections.abc import Callable

from inequality_mechanisms.graphs.adapters import ConstrainedInputSearchAdapter
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.heuristics import zero_heuristic
from inequality_mechanisms.search.result import SearchResult
from inequality_mechanisms.search.v1_compat import resolve_v1_default_edge_cost


def dijkstra(
    graph: ConstrainedInputGraph,
    start: int,
    goal: int,
    *,
    edge_cost: Callable[[int, int], float] | None = None,
    record_expanded: bool = False,
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
    record_expanded :
        Forwarded to ``best_first_search`` for diagnostic expanded-node masks.

    Returns
    -------
    SearchResult
        Optimal path and instrumentation counters.
    """
    cost_fn = (
        edge_cost if edge_cost is not None else resolve_v1_default_edge_cost(graph)
    )
    return best_first_search(
        ConstrainedInputSearchAdapter(graph),
        start,
        goal,
        edge_cost=cost_fn,
        heuristic=zero_heuristic,
        record_expanded=record_expanded,
    )
