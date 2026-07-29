"""Best-first search core shared by Dijkstra and A*.

See ``docs/ADR-005-search-semantics.md`` for expansion counting, stale-entry
handling, and deterministic tie-breaking.

Sprint V2.1 decouples this module from Version 1 graph types: it depends
only on the minimal :class:`~inequality_mechanisms.search.protocol.SearchGraph`
structural contract (node count, node validity, neighbor iteration) plus
explicit ``edge_cost`` and ``heuristic`` callables supplied by the caller.
This module imports only the generic search protocol; Version 1 adapters and
helpers live in ``graphs/adapters.py`` and ``search/v1_compat.py``.
"""

from __future__ import annotations

import heapq
import math

from inequality_mechanisms.search.protocol import EdgeCost, Heuristic, SearchGraph
from inequality_mechanisms.search.result import SearchResult


def _reconstruct_path(came_from: dict[int, int], goal: int) -> tuple[int, ...]:
    path: list[int] = [goal]
    current = goal
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return tuple(path)


def best_first_search(
    graph: SearchGraph,
    start: int,
    goal: int,
    *,
    edge_cost: EdgeCost,
    heuristic: Heuristic,
    record_expanded: bool = False,
) -> SearchResult:
    """Run instrumented best-first search on a generic search graph.

    Priority key is ``(f, node_id)`` with ``f = g + h(node)``. Equal ``f``
    values break ties by ascending flat ``node_id``. Multiple heap entries per
    node are allowed; a pop is **stale** when its ``g`` is strictly greater
    than the best-known ``g`` for that node and is not counted as an expansion.

    Parameters
    ----------
    graph :
        Any object satisfying :class:`SearchGraph` (node count, node
        validity, and neighbor iteration by flat node id).
    start, goal :
        Flat node ids. Both must be valid nodes of ``graph``.
    edge_cost :
        Required ``(u_id, v_id) -> float`` edge weight. The generic core
        constructs no graph-specific default; callers resolve one (e.g.
        Version 1's output Euclidean cost) before calling this function.
    heuristic :
        Cost-to-go estimate ``h(node_id)``. Use a zero heuristic for
        Dijkstra and an admissible heuristic for A*.
    record_expanded :
        When ``True``, populate ``SearchResult.expanded_nodes`` in expansion
        order (diagnostic views). Default keeps the tuple empty.

    Returns
    -------
    SearchResult
        Path, optimal cost, and instrumentation counters.

    Raises
    ------
    ValueError
        If ``start`` or ``goal`` is out of range or not a valid node.
    """
    n_nodes = graph.node_count
    if start < 0 or start >= n_nodes:
        raise ValueError(f"start node_id out of range: {start}")
    if goal < 0 or goal >= n_nodes:
        raise ValueError(f"goal node_id out of range: {goal}")
    if not graph.node_is_valid(start):
        raise ValueError(f"start node {start} is not valid under graph constraints")
    if not graph.node_is_valid(goal):
        raise ValueError(f"goal node {goal} is not valid under graph constraints")

    cost_fn = edge_cost

    g_best: dict[int, float] = {start: 0.0}
    came_from: dict[int, int] = {}
    # Heap entries: (f, node_id, g). Tie-break on node_id only.
    open_heap: list[tuple[float, int, float]] = []
    h_start = float(heuristic(start))
    if not math.isfinite(h_start) or h_start < 0.0:
        raise ValueError(f"heuristic(start) must be finite and >= 0, got {h_start}")
    heapq.heappush(open_heap, (h_start, start, 0.0))
    n_generated = 1
    n_expanded = 0
    n_stale = 0
    closed: set[int] = set()
    expanded_order: list[int] = []

    while open_heap:
        f_u, u, g_u = heapq.heappop(open_heap)
        del f_u  # used only for ordering
        best = g_best.get(u, math.inf)
        if g_u > best:
            n_stale += 1
            continue
        if u in closed:
            # Duplicate best-g entry; already expanded.
            n_stale += 1
            continue

        # Expansion: pop at best-known g and examine outgoing edges.
        n_expanded += 1
        closed.add(u)
        if record_expanded:
            expanded_order.append(u)

        if u == goal:
            path = _reconstruct_path(came_from, goal)
            return SearchResult(
                found=True,
                path=path,
                cost=float(g_best[goal]),
                n_expanded=n_expanded,
                n_generated=n_generated,
                n_stale=n_stale,
                expanded_nodes=tuple(expanded_order) if record_expanded else (),
            )

        for v in graph.neighbors(u):
            if v in closed:
                continue
            tentative = g_u + cost_fn(u, v)
            if not math.isfinite(tentative) or tentative < 0.0:
                raise ValueError(
                    f"edge cost from {u} to {v} produced non-finite or "
                    f"negative path cost {tentative}"
                )
            prev = g_best.get(v, math.inf)
            if tentative < prev:
                g_best[v] = tentative
                came_from[v] = u
                h_v = float(heuristic(v))
                if not math.isfinite(h_v) or h_v < 0.0:
                    raise ValueError(
                        f"heuristic({v}) must be finite and >= 0, got {h_v}"
                    )
                heapq.heappush(open_heap, (tentative + h_v, v, tentative))
                n_generated += 1

    return SearchResult(
        found=False,
        path=(),
        cost=math.inf,
        n_expanded=n_expanded,
        n_generated=n_generated,
        n_stale=n_stale,
        expanded_nodes=tuple(expanded_order) if record_expanded else (),
    )
