from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.v2_objectives import (
    input_euclidean_goal_set_heuristic_v2,
    resolve_v2_goal_set_objective,
)


class LineGraph:
    def __init__(self) -> None:
        self._u = np.asarray([[0.0], [1.0], [2.0], [3.0], [4.0]])
        self.branch = SimpleNamespace(output_space=None)
        self.topology = None

    @property
    def node_count(self) -> int:
        return len(self._u)

    def node_is_valid(self, node_id: int) -> bool:
        return 0 <= node_id < self.node_count

    def neighbors(self, node_id: int):
        out = []
        if node_id > 0:
            out.append(node_id - 1)
        if node_id + 1 < self.node_count:
            out.append(node_id + 1)
        return tuple(out)

    def u_state(self, node_id: int):
        return self._u[node_id]

    def q_state(self, node_id: int):
        return self._u[node_id]


def test_goal_set_heuristic_is_zero_on_goals_and_consistent() -> None:
    graph = LineGraph()
    goals = {1, 4}
    h = input_euclidean_goal_set_heuristic_v2(graph, goals)
    assert h(1) == 0.0
    assert h(4) == 0.0
    exact_distance = {0: 1.0, 1: 0.0, 2: 1.0, 3: 1.0, 4: 0.0}
    for a in range(graph.node_count):
        assert h(a) <= exact_distance[a] + 1e-12
        for b in graph.neighbors(a):
            cost = float(np.linalg.norm(graph.u_state(b) - graph.u_state(a)))
            assert h(a) <= cost + h(b) + 1e-12


def test_goal_set_astar_matches_dijkstra_and_expands_no_more() -> None:
    graph = LineGraph()
    goals = {3, 4}
    dijkstra_obj = resolve_v2_goal_set_objective(
        graph, goals, heuristic_name="zero"
    )
    astar_obj = resolve_v2_goal_set_objective(
        graph, goals, heuristic_name="input_euclidean_goal_set"
    )
    dijkstra = best_first_search(
        graph,
        0,
        None,
        goal_node_ids=goals,
        edge_cost=dijkstra_obj.edge_cost,
        heuristic=dijkstra_obj.heuristic,
    )
    astar = best_first_search(
        graph,
        0,
        None,
        goal_node_ids=goals,
        edge_cost=astar_obj.edge_cost,
        heuristic=astar_obj.heuristic,
    )
    assert astar.cost == dijkstra.cost
    assert astar.selected_goal_node_id == dijkstra.selected_goal_node_id == 3
    assert astar.path[-1] == dijkstra.path[-1] == 3
    assert astar.n_expanded <= dijkstra.n_expanded
