"""V4.2B Phase 1: invalid local motion is filtered before search (V4-225)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from inequality_mechanisms.search.core import best_first_search


@dataclass
class TinyGraph:
    """Minimal SearchGraph with explicit adjacency."""

    _node_count: int
    _adj: dict[int, tuple[int, ...]]

    @property
    def node_count(self) -> int:
        return self._node_count

    def node_is_valid(self, node_id: int) -> bool:
        return 0 <= int(node_id) < self._node_count

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        return self._adj.get(int(node_id), ())


def test_generic_search_still_rejects_nonfinite_supplied_weights() -> None:
    graph = TinyGraph(3, {0: (1, 2), 1: (2,), 2: ()})

    def inf_cost(u: int, v: int) -> float:
        if (u, v) == (0, 2):
            return math.inf
        return 1.0

    with pytest.raises(ValueError, match="non-finite|negative"):
        best_first_search(
            graph,
            0,
            2,
            edge_cost=inf_cost,
            heuristic=lambda _node: 0.0,
        )


def test_finite_route_is_used_after_unavailable_local_motion_is_filtered() -> None:
    from inequality_mechanisms.adapters.finite_search_edges import compile_finite_neighbors

    raw = TinyGraph(3, {0: (1, 2), 1: (2,), 2: ()})

    def raw_cost(u: int, v: int) -> float:
        if (u, v) == (0, 2):
            return math.inf
        return 1.0

    compiled = compile_finite_neighbors(raw, raw_cost)
    assert compiled.rejected_candidates[(0, 2)]["candidate_edge_status"] == (
        "unavailable_local_motion"
    )
    dijkstra = best_first_search(
        compiled.graph,
        0,
        2,
        edge_cost=compiled.edge_cost,
        heuristic=lambda _node: 0.0,
    )
    astar = best_first_search(
        compiled.graph,
        0,
        2,
        edge_cost=compiled.edge_cost,
        heuristic=lambda node: float(abs(2 - node)),
    )
    assert dijkstra.found is True
    assert astar.found is True
    assert dijkstra.cost == pytest.approx(astar.cost)
    assert dijkstra.cost == pytest.approx(2.0)
    assert 2 not in tuple(compiled.graph.neighbors(0))


def test_all_unavailable_routes_return_found_false() -> None:
    from inequality_mechanisms.adapters.finite_search_edges import compile_finite_neighbors

    raw = TinyGraph(2, {0: (1,), 1: ()})

    def all_inf(_u: int, _v: int) -> float:
        return math.inf

    compiled = compile_finite_neighbors(raw, all_inf)
    result = best_first_search(
        compiled.graph,
        0,
        1,
        edge_cost=compiled.edge_cost,
        heuristic=lambda _node: 0.0,
    )
    assert result.found is False
    assert result.selected_goal_node_id is None
