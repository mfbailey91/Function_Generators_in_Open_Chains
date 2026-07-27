"""Tests for reverse-search heuristic quality diagnostics (S4-04)."""

from __future__ import annotations

import pytest

from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.search import (
    dijkstra,
    heuristic_quality_report,
    resolve_planning_objective,
    zero_heuristic,
)
from inequality_mechanisms.spaces import OutputJointLimits


def _unit_graph() -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(
        (5, 5),
        ranges=((0.0, 5.0), (0.0, 5.0)),
        wrap=(False, False),
    )
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[5.0, 5.0])
    return ConstrainedInputGraph(grid, mech, limits)


class TestHeuristicQuality:
    @pytest.mark.parametrize(
        "cost_name",
        ["uniform", "input_euclidean", "output_euclidean"],
    )
    def test_default_heuristic_admissible(self, cost_name: str) -> None:
        graph = _unit_graph()
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(3, 2)
        obj = resolve_planning_objective(graph, goal, cost_name)
        result = dijkstra(graph, start, goal, edge_cost=obj.edge_cost)
        report = heuristic_quality_report(
            graph,
            goal,
            obj.heuristic,
            edge_cost=obj.edge_cost,
            cost_name=obj.cost_name,
            heuristic_name=obj.heuristic_name,
            path=result.path,
        )
        assert report.admissible is True
        assert report.failure_reason is None
        assert report.n_sampled > 0
        assert report.mean_error >= -1e-12

    def test_zero_heuristic_strength_near_zero(self) -> None:
        graph = _unit_graph()
        goal = graph.grid.node_id(2, 2)
        obj = resolve_planning_objective(
            graph, goal, "output_euclidean", heuristic_name="zero"
        )
        report = heuristic_quality_report(
            graph,
            goal,
            zero_heuristic,
            edge_cost=obj.edge_cost,
            cost_name="output_euclidean",
            heuristic_name="zero",
        )
        assert report.admissible is True
        assert report.mean_strength == pytest.approx(0.0)

    def test_seeded_sampling_reproducible(self) -> None:
        graph = _unit_graph()
        goal = graph.grid.node_id(4, 4)
        obj = resolve_planning_objective(graph, goal, "uniform")
        kwargs = dict(
            edge_cost=obj.edge_cost,
            cost_name="uniform",
            heuristic_name="uniform_step",
            max_sample_nodes=8,
            sample_seed=42,
        )
        a = heuristic_quality_report(graph, goal, obj.heuristic, **kwargs)
        b = heuristic_quality_report(graph, goal, obj.heuristic, **kwargs)
        assert a.to_dict() == b.to_dict()
        assert a.n_sampled == 8
        assert a.sample_seed == 42
