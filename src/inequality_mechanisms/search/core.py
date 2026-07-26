"""Best-first search core shared by Dijkstra and A*.

See ``docs/ADR-005-search-semantics.md`` for expansion counting, stale-entry
handling, and deterministic tie-breaking.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.heuristics import Heuristic
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
    graph: ConstrainedInputGraph,
    start: int,
    goal: int,
    heuristic: Heuristic,
    *,
    edge_cost: Callable[[int, int], float] | None = None,
) -> SearchResult:
    """Run instrumented best-first search on a constrained input graph.

    Priority key is ``(f, node_id)`` with ``f = g + h(node)``. Equal ``f``
    values break ties by ascending flat ``node_id``. Multiple heap entries per
    node are allowed; a pop is **stale** when its ``g`` is strictly greater
    than the best-known ``g`` for that node and is not counted as an expansion.

    Parameters
    ----------
    graph :
        Filtered input lattice with mechanism and shared output limits.
    start, goal :
        Flat node ids. Both must be valid nodes of ``graph``.
    heuristic :
        Cost-to-go estimate ``h(node_id)``. Use ``zero_heuristic`` for
        Dijkstra and an output-space Euclidean heuristic for A*.
    edge_cost :
        Optional ``(u_id, v_id) -> float`` override. Defaults to Version 1
        output Euclidean displacement.

    Returns
    -------
    SearchResult
        Path, optimal cost, and instrumentation counters.

    Raises
    ------
    ValueError
        If ``start`` or ``goal`` is out of range or not a valid node.
    """
    n_nodes = graph.grid.node_count
    if start < 0 or start >= n_nodes:
        raise ValueError(f"start node_id out of range: {start}")
    if goal < 0 or goal >= n_nodes:
        raise ValueError(f"goal node_id out of range: {goal}")
    if not graph.node_is_valid_id(start):
        raise ValueError(f"start node {start} is not valid under graph constraints")
    if not graph.node_is_valid_id(goal):
        raise ValueError(f"goal node {goal} is not valid under graph constraints")

    cost_fn = edge_cost
    if cost_fn is None:
        grid = graph.grid

        def cost_fn(u_id: int, v_id: int) -> float:
            u = grid.indices_from_id(u_id)
            v = grid.indices_from_id(v_id)
            # IM-042: graph owns raw → canonical conversion for edge costs.
            return graph.output_displacement(
                grid.coordinates(*u),
                grid.coordinates(*v),
            )

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

        if u == goal:
            path = _reconstruct_path(came_from, goal)
            return SearchResult(
                found=True,
                path=path,
                cost=float(g_best[goal]),
                n_expanded=n_expanded,
                n_generated=n_generated,
                n_stale=n_stale,
            )

        i0, i1 = graph.grid.indices_from_id(u)
        for j0, j1 in graph.neighbors(i0, i1):
            v = graph.grid.node_id(j0, j1)
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
    )


def _cached_outputs(
    graph: ConstrainedInputGraph,
) -> Callable[[int], NDArray[np.floating]]:
    """Lazily cache canonicalized ``g(u)`` by flat node id."""
    cache: dict[int, NDArray[np.floating]] = {}

    def output_of(node_id: int) -> NDArray[np.floating]:
        cached = cache.get(node_id)
        if cached is not None:
            return cached
        coords = graph.grid.coordinates(*graph.grid.indices_from_id(node_id))
        q = graph.output(coords)
        cache[node_id] = q
        return q

    return output_of
