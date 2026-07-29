"""Tests for path length metrics and cost invariants (S4-03 / S5-01)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.graphs.costs import wrapped_input_displacement
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.metrics.path_metrics import (
    PATH_LENGTH_CONVENTIONS,
    assert_cost_path_invariant,
    compute_path_metrics,
    compute_path_metrics_from_trajectories,
)
from inequality_mechanisms.search import dijkstra, resolve_planning_objective
from inequality_mechanisms.spaces import OutputJointLimits, OutputSpace


def _unit_graph(*, wrap: tuple[bool, bool] = (False, False)) -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(
        (6, 6),
        ranges=((0.0, 6.0), (0.0, 6.0)),
        wrap=wrap,
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

    def test_one_edge_path(self) -> None:
        graph = _unit_graph()
        a = graph.grid.node_id(1, 1)
        b = graph.grid.node_id(2, 1)
        metrics = compute_path_metrics(graph, (a, b), optimal_cost=1.0)
        assert metrics.n_path_edges == 1
        assert metrics.path_length_u == pytest.approx(1.0)
        assert metrics.path_length_q == pytest.approx(1.0)

    def test_straight_discrete_path(self) -> None:
        graph = _unit_graph()
        nodes = [graph.grid.node_id(i, 1) for i in range(1, 5)]
        metrics = compute_path_metrics(graph, nodes, optimal_cost=3.0)
        assert metrics.n_path_edges == 3
        assert metrics.path_length_u == pytest.approx(3.0)
        assert metrics.path_length_q == pytest.approx(3.0)

    def test_periodic_input_seam_crossing(self) -> None:
        from inequality_mechanisms.visualization.paths import path_inputs

        graph = _unit_graph(wrap=(True, True))
        shape = graph.grid.shape
        a = graph.grid.node_id(shape[0] - 1, 1)
        b = graph.grid.node_id(0, 1)
        metrics = compute_path_metrics(graph, (a, b), optimal_cost=1.0)
        u_path = path_inputs(graph, [a, b])
        expected = wrapped_input_displacement(
            u_path[0], u_path[1], wrap=(True, True)
        )
        assert metrics.path_length_u == pytest.approx(expected)
        assert metrics.path_length_u < abs(float(u_path[1, 0] - u_path[0, 0])) + 1e-9

    def test_identical_lu_different_lq(self) -> None:
        u = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], dtype=np.float64)
        q_short = np.array([[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]], dtype=np.float64)
        q_long = np.array([[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]], dtype=np.float64)
        m_short = compute_path_metrics_from_trajectories(
            u, q_short, optimal_cost=2.0, wrap_u=(False, False)
        )
        m_long = compute_path_metrics_from_trajectories(
            u, q_long, optimal_cost=2.0, wrap_u=(False, False)
        )
        assert m_short.path_length_u == pytest.approx(m_long.path_length_u)
        assert m_short.path_length_q != pytest.approx(m_long.path_length_q)

    def test_identical_lq_different_lx(self) -> None:
        u = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]], dtype=np.float64)
        q = np.array(
            [[0.0, 0.0], [np.pi / 2, 0.0], [np.pi, 0.0]],
            dtype=np.float64,
        )
        m1 = compute_path_metrics_from_trajectories(
            u, q, optimal_cost=0.0, plant=Planar2R(L1=1.0, L2=1.0)
        )
        m2 = compute_path_metrics_from_trajectories(
            u, q, optimal_cost=0.0, plant=Planar2R(L1=2.0, L2=2.0)
        )
        assert m1.path_length_q == pytest.approx(m2.path_length_q)
        assert m1.path_length_x != pytest.approx(m2.path_length_x)

    def test_lq_uses_output_space_distance(self) -> None:
        space = OutputSpace.from_limits(
            OutputJointLimits.box(lower=[0.0, 0.0], upper=[6.0, 6.0])
        )
        u = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float64)
        q = np.array([[1.0, 1.0], [2.0, 1.0]], dtype=np.float64)
        metrics = compute_path_metrics_from_trajectories(
            u, q, optimal_cost=1.0, output_space=space
        )
        assert metrics.path_length_q == pytest.approx(space.distance(q[0], q[1]))

    def test_conventions_documented(self) -> None:
        assert "path_length_u" in PATH_LENGTH_CONVENTIONS
        assert "path_length_q" in PATH_LENGTH_CONVENTIONS
        assert "path_length_x" in PATH_LENGTH_CONVENTIONS
