"""Tests for PlanningObjective resolver and cost/heuristic pairs (S4-02)."""

from __future__ import annotations

import pytest

from inequality_mechanisms.graphs import (
    ConstrainedInputGraph,
    ConstrainedInputSearchAdapter,
    PeriodicGrid2D,
)
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.search import (
    astar,
    dijkstra,
    resolve_planning_objective,
)
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.spaces import OutputJointLimits


def _unit_graph(
    shape: tuple[int, int] = (6, 6),
    *,
    wrap: tuple[bool, bool] = (False, False),
    upper: float = 6.0,
) -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(shape, ranges=((0.0, upper), (0.0, upper)), wrap=wrap)
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[upper, upper])
    return ConstrainedInputGraph(grid, mech, limits)


class TestPlanningObjectives:
    @pytest.mark.parametrize(
        "cost_name",
        ["uniform", "input_euclidean", "output_euclidean"],
    )
    def test_dijkstra_matches_astar_cost(self, cost_name: str) -> None:
        graph = _unit_graph()
        start = graph.grid.node_id(1, 1)
        goal = graph.grid.node_id(4, 2)
        obj = resolve_planning_objective(graph, goal, cost_name)
        d = dijkstra(graph, start, goal, edge_cost=obj.edge_cost)
        a = best_first_search(
            ConstrainedInputSearchAdapter(graph),
            start,
            goal,
            edge_cost=obj.edge_cost,
            heuristic=obj.heuristic,
        )
        assert d.found and a.found
        assert d.cost == pytest.approx(a.cost)

    def test_astar_refuses_custom_edge_cost(self) -> None:
        graph = _unit_graph()
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(1, 0)
        obj = resolve_planning_objective(graph, goal, "uniform")
        with pytest.raises(ValueError, match="custom edge_cost"):
            astar(graph, start, goal, edge_cost=obj.edge_cost)

    def test_incompatible_heuristic_rejected(self) -> None:
        graph = _unit_graph()
        goal = graph.grid.node_id(1, 1)
        with pytest.raises(ValueError, match="incompatible"):
            resolve_planning_objective(
                graph, goal, "uniform", heuristic_name="output_euclidean"
            )

    def test_zero_always_allowed(self) -> None:
        graph = _unit_graph()
        goal = graph.grid.node_id(1, 1)
        for cost in ("uniform", "input_euclidean", "output_euclidean"):
            obj = resolve_planning_objective(
                graph, goal, cost, heuristic_name="zero"
            )
            assert obj.heuristic_name == "zero"
            assert obj.heuristic(goal) == pytest.approx(0.0)

    def test_unknown_cost_rejected(self) -> None:
        graph = _unit_graph()
        goal = graph.grid.node_id(0, 0)
        with pytest.raises(ValueError, match="unknown cost"):
            resolve_planning_objective(graph, goal, "custom_torque")
