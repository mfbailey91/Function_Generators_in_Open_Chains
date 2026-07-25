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
    """Compute an optimal path with ``f = g + d_Q(q_n, q_goal)``.

    The goal output ``q_goal = canonicalize(g(u_goal))`` is taken from the
    goal node so ``h(goal) = 0``. With Version 1 output Euclidean edge costs
    the heuristic is consistent, so the first expansion of the goal yields
    ``C*``.

    Parameters
    ----------
    graph :
        Constrained input lattice.
    start, goal :
        Flat valid node ids (known preimages in Version 1 trials).
    edge_cost :
        Optional edge-weight override; default is output Euclidean cost.
        Custom costs must not silently reuse the default output heuristic
        (ADR-005 / IM-035): pass a compatible heuristic via
        ``best_first_search`` or use Dijkstra / ``zero_heuristic``.

    Returns
    -------
    SearchResult
        Optimal path and instrumentation counters.

    Raises
    ------
    ValueError
        If a custom ``edge_cost`` is supplied (caller must use
        ``best_first_search`` with an explicit compatible heuristic).
    """
    if edge_cost is not None:
        raise ValueError(
            "astar() refuses a custom edge_cost with the default output "
            "heuristic; use best_first_search(..., heuristic=...) with a "
            "documented compatible heuristic, or dijkstra() / zero_heuristic"
        )
    output_of = _cached_outputs(graph)
    q_goal = output_of(goal)
    heuristic = output_euclidean_heuristic(
        graph.mechanism,
        q_goal,
        output_of,
        output_space=graph.output_space,
    )
    return best_first_search(
        graph,
        start,
        goal,
        heuristic,
        edge_cost=None,
    )
