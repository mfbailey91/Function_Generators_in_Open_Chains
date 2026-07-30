"""Version 2 objective registry tests (Sprint V2.4, V2-404)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch, gearbox_2d_branch

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.v2_objectives import (
    KNOWN_V2_COST_TYPES,
    compatible_v2_heuristic_names,
    default_v2_heuristic_name,
    input_euclidean_edge_cost,
    output_euclidean_edge_cost,
    resolve_v2_objective,
    uniform_edge_cost_v2,
    uniform_step_heuristic_v2,
    zero_heuristic_v2,
)


def _gearbox_graph() -> EmbeddedPlanningGraph:
    return EmbeddedPlanningGraph.from_uniform_input(gearbox_2d_branch(), shape=(5, 5))


class TestCompatibilityTable:
    def test_known_costs(self) -> None:
        # Sprint V2.4 requires exactly these three; later sprints (e.g.
        # V2.6 capability costs) may register additional names, so this
        # checks a required subset rather than exact equality.
        assert {"uniform", "output_euclidean", "input_euclidean"} <= KNOWN_V2_COST_TYPES

    @pytest.mark.parametrize(
        "cost,expected_default",
        [
            ("uniform", "uniform_step"),
            ("output_euclidean", "output_euclidean"),
            ("input_euclidean", "input_euclidean"),
        ],
    )
    def test_default_heuristic(self, cost: str, expected_default: str) -> None:
        assert default_v2_heuristic_name(cost) == expected_default

    @pytest.mark.parametrize("cost", ["uniform", "output_euclidean", "input_euclidean"])
    def test_zero_always_allowed(self, cost: str) -> None:
        assert "zero" in compatible_v2_heuristic_names(cost)

    def test_output_heuristic_incompatible_with_input_cost(self) -> None:
        assert "output_euclidean" not in compatible_v2_heuristic_names(
            "input_euclidean"
        )

    def test_input_heuristic_incompatible_with_output_cost(self) -> None:
        assert "input_euclidean" not in compatible_v2_heuristic_names(
            "output_euclidean"
        )

    def test_unknown_cost_raises(self) -> None:
        with pytest.raises(ValueError):
            compatible_v2_heuristic_names("capability_energy")


class TestResolveV2Objective:
    def test_rejects_incompatible_heuristic(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        with pytest.raises(ValueError, match="incompatible"):
            resolve_v2_objective(graph, goal, "output_euclidean", "input_euclidean")

    def test_rejects_unknown_cost(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        with pytest.raises(ValueError, match="unknown"):
            resolve_v2_objective(graph, goal, "capability_energy")

    def test_defaults_to_compatible_heuristic(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        objective = resolve_v2_objective(graph, goal, "output_euclidean")
        assert objective.heuristic_name == "output_euclidean"

    def test_output_heuristic_is_zero_at_goal(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        objective = resolve_v2_objective(graph, goal, "output_euclidean")
        assert objective.heuristic(goal) == pytest.approx(0.0, abs=1e-12)

    def test_input_heuristic_is_zero_at_goal(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        objective = resolve_v2_objective(graph, goal, "input_euclidean")
        assert objective.heuristic(goal) == pytest.approx(0.0, abs=1e-12)

    def test_actuator_travel_defaults_to_input_euclidean_heuristic(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        objective = resolve_v2_objective(graph, goal, "actuator_travel")
        assert objective.heuristic_name == "input_euclidean"

    def test_gain_resolution_allows_only_zero_heuristic(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        with pytest.raises(ValueError, match="incompatible"):
            resolve_v2_objective(graph, goal, "gain_resolution", "input_euclidean")
        objective = resolve_v2_objective(graph, goal, "gain_resolution")
        assert objective.heuristic_name == "zero"
        assert objective.heuristic(goal) == pytest.approx(0.0, abs=1e-12)


class TestEdgeCostCorrectness:
    def test_output_euclidean_matches_output_space_distance(self) -> None:
        graph = _gearbox_graph()
        cost = output_euclidean_edge_cost(graph)
        a, b = graph.topology.node_id((0, 0)), graph.topology.node_id((0, 1))
        expected = graph.branch.output_space.distance(
            graph.q_state(a), graph.q_state(b)
        )
        assert cost(a, b) == pytest.approx(expected)

    def test_input_euclidean_matches_raw_norm(self) -> None:
        graph = _gearbox_graph()
        cost = input_euclidean_edge_cost(graph)
        a, b = graph.topology.node_id((0, 0)), graph.topology.node_id((0, 1))
        expected = float(np.linalg.norm(graph.u_state(b) - graph.u_state(a)))
        assert cost(a, b) == pytest.approx(expected)

    def test_uniform_cost_is_one(self) -> None:
        assert uniform_edge_cost_v2(0, 1) == 1.0


class TestUniformStepHeuristicAdmissible:
    def test_never_overestimates_true_hop_count(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        h = uniform_step_heuristic_v2(graph, goal)
        for start in range(graph.node_count):
            if not graph.node_is_valid(start):
                continue
            true_cost = best_first_search(
                graph,
                start,
                goal,
                edge_cost=uniform_edge_cost_v2,
                heuristic=zero_heuristic_v2,
            ).cost
            assert h(start) <= true_cost + 1e-9

    def test_zero_at_goal(self) -> None:
        graph = _gearbox_graph()
        goal = graph.topology.node_id((4, 4))
        h = uniform_step_heuristic_v2(graph, goal)
        assert h(goal) == 0.0


class TestDijkstraAstarAgreement:
    @pytest.mark.parametrize(
        "cost_name",
        ["uniform", "output_euclidean", "input_euclidean", "actuator_travel"],
    )
    def test_astar_matches_dijkstra_optimal_cost(self, cost_name: str) -> None:
        graph = _gearbox_graph()
        start = graph.topology.node_id((0, 0))
        goal = graph.topology.node_id((4, 4))

        dijkstra_objective = resolve_v2_objective(graph, goal, cost_name, "zero")
        dijkstra_result = best_first_search(
            graph,
            start,
            goal,
            edge_cost=dijkstra_objective.edge_cost,
            heuristic=zero_heuristic_v2,
        )

        astar_objective = resolve_v2_objective(graph, goal, cost_name)
        astar_result = best_first_search(
            graph,
            start,
            goal,
            edge_cost=astar_objective.edge_cost,
            heuristic=astar_objective.heuristic,
        )

        assert dijkstra_result.found
        assert astar_result.found
        assert astar_result.cost == pytest.approx(dijkstra_result.cost, abs=1e-9)

    def test_fourbar_and_gearbox_agree_when_heuristics_admissible(self) -> None:
        for branch in (fourbar_2d_branch(), gearbox_2d_branch()):
            graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(5, 5))
            start = graph.topology.node_id((0, 0))
            goal = graph.topology.node_id((4, 4))
            objective = resolve_v2_objective(graph, goal, "output_euclidean")
            dijkstra_result = best_first_search(
                graph,
                start,
                goal,
                edge_cost=objective.edge_cost,
                heuristic=zero_heuristic_v2,
            )
            astar_result = best_first_search(
                graph,
                start,
                goal,
                edge_cost=objective.edge_cost,
                heuristic=objective.heuristic,
            )
            assert astar_result.cost == pytest.approx(dijkstra_result.cost, abs=1e-9)


class TestGainResolutionSmoke:
    def test_gain_resolution_finds_path_with_zero_heuristic(self) -> None:
        graph = EmbeddedPlanningGraph.from_uniform_input(
            gearbox_2d_branch(), shape=(4, 4)
        )
        start = graph.topology.node_id((0, 0))
        goal = graph.topology.node_id((3, 3))

        objective = resolve_v2_objective(graph, goal, "gain_resolution")
        result = best_first_search(
            graph,
            start,
            goal,
            edge_cost=objective.edge_cost,
            heuristic=objective.heuristic,
        )
        assert result.found
        assert result.cost >= 0.0
