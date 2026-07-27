"""Tests for path length metrics and cost invariants (S4-03)."""

from __future__ import annotations

import pytest

from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.metrics.path_metrics import (
    assert_cost_path_invariant,
    compute_path_metrics,
)
from inequality_mechanisms.search import dijkstra, resolve_planning_objective
from inequality_mechanisms.spaces import OutputJointLimits


def _unit_graph() -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(
        (6, 6),
        ranges=((0.0, 6.0), (0.0, 6.0)),
        wrap=(False, False),
    )
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[6.0, 6.0])
    return ConstrainedInputGraph(grid, mech, limits)


class TestPathMetrics:
    @pytest.mark.parametrize(
        "cost_name",
        ["uniform", "input_euclidean", "output_euclidean"],
    )
    def test_cost_matches_path_length(self, cost_name: str) -> None:
        graph = _unit_graph()
        start = graph.grid.node_id(1, 1)
        goal = graph.grid.node_id(4, 2)
        obj = resolve_planning_objective(graph, goal, cost_name)
        result = dijkstra(graph, start, goal, edge_cost=obj.edge_cost)
        assert result.found
        metrics = compute_path_metrics(
            graph, result.path, optimal_cost=float(result.cost)
        )
        assert metrics.n_path_edges == result.n_path_edges
        assert_cost_path_invariant(cost_name, metrics)
        assert metrics.path_length_x >= 0.0

    def test_empty_path(self) -> None:
        graph = _unit_graph()
        node = graph.grid.node_id(1, 1)
        metrics = compute_path_metrics(graph, (node,), optimal_cost=0.0)
        assert metrics.n_path_edges == 0
        assert metrics.path_length_u == pytest.approx(0.0)
        assert metrics.path_length_q == pytest.approx(0.0)
        assert metrics.path_length_x == pytest.approx(0.0)
