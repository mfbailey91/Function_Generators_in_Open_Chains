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


def _compile_single_edge(weight: float):
    from inequality_mechanisms.adapters.finite_search_edges import (
        compile_finite_neighbors,
    )

    raw = TinyGraph(2, {0: (1,), 1: ()})
    return compile_finite_neighbors(raw, lambda _u, _v: weight)


def test_positive_infinity_is_omitted_as_unavailable_local_motion() -> None:
    compiled = _compile_single_edge(math.inf)
    assert compiled.rejected_candidates[(0, 1)]["candidate_edge_status"] == (
        "unavailable_local_motion"
    )
    assert 1 not in tuple(compiled.graph.neighbors(0))


def test_nan_edge_cost_raises() -> None:
    with pytest.raises(ValueError, match="NaN"):
        _compile_single_edge(math.nan)


def test_negative_infinity_edge_cost_raises() -> None:
    with pytest.raises(ValueError, match="negative infinity"):
        _compile_single_edge(-math.inf)


def test_finite_negative_edge_cost_raises() -> None:
    with pytest.raises(ValueError, match="negative"):
        _compile_single_edge(-1.0)


def test_zero_edge_cost_is_admitted() -> None:
    compiled = _compile_single_edge(0.0)
    assert compiled.rejected_candidates == {}
    assert tuple(compiled.graph.neighbors(0)) == (1,)
    assert compiled.edge_cost(0, 1) == pytest.approx(0.0)


def test_positive_finite_edge_cost_is_admitted() -> None:
    compiled = _compile_single_edge(2.5)
    assert compiled.rejected_candidates == {}
    assert tuple(compiled.graph.neighbors(0)) == (1,)
    assert compiled.edge_cost(0, 1) == pytest.approx(2.5)
