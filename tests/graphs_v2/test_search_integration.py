"""EmbeddedPlanningGraph satisfies the generic SearchGraph contract."""

from __future__ import annotations

import math

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch, gearbox_2d_branch

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.search import best_first_search, zero_heuristic
from inequality_mechanisms.search.protocol import SearchGraph


def _output_euclidean_cost(graph: EmbeddedPlanningGraph):
    def cost(a: int, b: int) -> float:
        return float(np.linalg.norm(graph.q_state(b) - graph.q_state(a)))

    return cost


class TestSearchGraphProtocol:
    def test_isinstance_check(self) -> None:
        graph = EmbeddedPlanningGraph.from_uniform_input(
            gearbox_2d_branch(), shape=(4, 4)
        )
        assert isinstance(graph, SearchGraph)

    def test_dijkstra_finds_optimal_corner_to_corner_path(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(5, 5))
        start = graph.topology.node_id((0, 0))
        goal = graph.topology.node_id((4, 4))
        result = best_first_search(
            graph,
            start,
            goal,
            edge_cost=_output_euclidean_cost(graph),
            heuristic=zero_heuristic,
        )
        assert result.found
        assert result.path[0] == start
        assert result.path[-1] == goal
        # Path cost matches accumulated straight-line output distance.
        manual_cost = sum(
            float(np.linalg.norm(graph.q_state(b) - graph.q_state(a)))
            for a, b in zip(result.path[:-1], result.path[1:])
        )
        assert result.cost == pytest.approx(manual_cost)

    def test_search_over_uniform_output_fourbar_graph(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(6, 6))
        start = graph.topology.node_id((0, 0))
        goal = graph.topology.node_id((5, 5))
        result = best_first_search(
            graph,
            start,
            goal,
            edge_cost=_output_euclidean_cost(graph),
            heuristic=zero_heuristic,
        )
        assert result.found
        assert math.isfinite(result.cost)
        assert result.cost > 0.0
