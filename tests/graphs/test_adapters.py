"""Tests for ``ConstrainedInputSearchAdapter`` (Sprint V2.1, V2-104)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.graphs import (
    ConstrainedInputGraph,
    ConstrainedInputSearchAdapter,
    PeriodicGrid2D,
)
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.search.protocol import SearchGraph
from inequality_mechanisms.spaces import OutputJointLimits


def _unit_box_graph(
    shape: tuple[int, int] = (6, 6),
    *,
    wrap: tuple[bool, bool] = (False, False),
    upper: float = 6.0,
) -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(shape, ranges=((0.0, upper), (0.0, upper)), wrap=wrap)
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[upper, upper])
    return ConstrainedInputGraph(grid, mech, limits)


class TestConstrainedInputSearchAdapter:
    def test_satisfies_search_graph_protocol(self) -> None:
        graph = _unit_box_graph()
        adapter = ConstrainedInputSearchAdapter(graph)
        assert isinstance(adapter, SearchGraph)

    def test_node_count_matches_grid(self) -> None:
        graph = _unit_box_graph((5, 7), upper=5.0)
        adapter = ConstrainedInputSearchAdapter(graph)
        assert adapter.node_count == graph.grid.node_count

    def test_node_is_valid_matches_node_is_valid_id(self) -> None:
        graph = _unit_box_graph((6, 6), upper=6.0)
        adapter = ConstrainedInputSearchAdapter(graph)
        for node_id in range(graph.grid.node_count):
            assert adapter.node_is_valid(node_id) == graph.node_is_valid_id(node_id)

    def test_neighbors_match_index_based_neighbors(self) -> None:
        graph = _unit_box_graph((6, 6), upper=6.0)
        adapter = ConstrainedInputSearchAdapter(graph)
        for node_id in range(graph.grid.node_count):
            i0, i1 = graph.grid.indices_from_id(node_id)
            expected = tuple(
                graph.grid.node_id(j0, j1) for j0, j1 in graph.neighbors(i0, i1)
            )
            assert adapter.neighbors(node_id) == expected

    def test_neighbors_match_neighbors_by_id(self) -> None:
        graph = _unit_box_graph((5, 5), upper=5.0)
        adapter = ConstrainedInputSearchAdapter(graph)
        for node_id in range(graph.grid.node_count):
            assert adapter.neighbors(node_id) == graph.neighbors_by_id(node_id)

    def test_invalid_node_has_no_neighbors(self) -> None:
        grid = PeriodicGrid2D(
            (4, 4), ranges=((0.0, 2.0), (0.0, 2.0)), wrap=(False, False)
        )
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        adapter = ConstrainedInputSearchAdapter(graph)
        bad = graph.grid.node_id(3, 3)
        assert adapter.node_is_valid(bad) is False
        assert adapter.neighbors(bad) == ()

    def test_graph_property_returns_wrapped_graph(self) -> None:
        graph = _unit_box_graph()
        adapter = ConstrainedInputSearchAdapter(graph)
        assert adapter.graph is graph


class TestNeighborsById:
    def test_matches_two_index_neighbors(self) -> None:
        graph = _unit_box_graph((6, 6), upper=6.0)
        for node_id in range(graph.grid.node_count):
            i0, i1 = graph.grid.indices_from_id(node_id)
            expected = tuple(
                graph.grid.node_id(j0, j1) for j0, j1 in graph.neighbors(i0, i1)
            )
            assert graph.neighbors_by_id(node_id) == expected

    def test_invalid_node_returns_empty_tuple(self) -> None:
        grid = PeriodicGrid2D(
            (4, 4), ranges=((0.0, 2.0), (0.0, 2.0)), wrap=(False, False)
        )
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        bad = graph.grid.node_id(3, 3)
        assert graph.node_is_valid_id(bad) is False
        assert graph.neighbors_by_id(bad) == ()


class TestNodeCountProperty:
    def test_matches_grid_node_count(self) -> None:
        graph = _unit_box_graph((8, 3), upper=8.0)
        assert graph.node_count == graph.grid.node_count
        assert graph.node_count == np.prod(graph.grid.shape)


class TestSearchGraphProtocol:
    def test_bare_constrained_input_graph_node_is_valid_is_two_index(self) -> None:
        # ConstrainedInputGraph keeps its two-index API (node_is_valid(i0,
        # i1), neighbors(i0, i1)) unchanged (V2-104): calling node_is_valid
        # with a single flat id (the SearchGraph shape) is a TypeError,
        # even though `isinstance(graph, SearchGraph)` structurally passes
        # (runtime_checkable Protocol checks attribute names, not
        # signatures). The adapter, not the bare graph, is the intended
        # SearchGraph for search code.
        graph = _unit_box_graph()
        with pytest.raises(TypeError):
            graph.node_is_valid(0)  # type: ignore[call-arg]
