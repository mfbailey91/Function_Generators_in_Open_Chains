from __future__ import annotations

from dataclasses import dataclass

import pytest

from inequality_mechanisms.search.core import best_first_search


@dataclass
class TinyGraph:
    adjacency: dict[int, tuple[int, ...]]

    @property
    def node_count(self) -> int:
        return len(self.adjacency)

    def node_is_valid(self, node_id: int) -> bool:
        return node_id in self.adjacency

    def neighbors(self, node_id: int):
        return self.adjacency[node_id]


def edge_cost(a: int, b: int) -> float:
    weights = {
        frozenset({0, 1}): 1.0,
        frozenset({1, 2}): 1.0,
        frozenset({0, 3}): 1.0,
        frozenset({3, 4}): 4.0,
    }
    return weights[frozenset({a, b})]


def graph() -> TinyGraph:
    return TinyGraph(
        {
            0: (1, 3),
            1: (0, 2),
            2: (1,),
            3: (0, 4),
            4: (3,),
        }
    )


def test_single_goal_backward_compatibility() -> None:
    result = best_first_search(
        graph(), 0, 2, edge_cost=edge_cost, heuristic=lambda _n: 0.0
    )
    assert result.path == (0, 1, 2)
    assert result.cost == 2.0
    assert result.selected_goal_node_id == 2


def test_explicit_goal_set_selects_cheapest_settled_goal() -> None:
    result = best_first_search(
        graph(),
        0,
        None,
        goal_node_ids={2, 4},
        edge_cost=edge_cost,
        heuristic=lambda _n: 0.0,
    )
    assert result.path[-1] == 2
    assert result.selected_goal_node_id == 2
    assert result.cost == 2.0


def test_goal_predicate_matches_explicit_set() -> None:
    explicit = best_first_search(
        graph(),
        0,
        None,
        goal_node_ids={2, 4},
        edge_cost=edge_cost,
        heuristic=lambda _n: 0.0,
    )
    predicate = best_first_search(
        graph(),
        0,
        None,
        goal_test=lambda node_id: node_id in {2, 4},
        edge_cost=edge_cost,
        heuristic=lambda _n: 0.0,
    )
    assert predicate.path == explicit.path
    assert predicate.cost == explicit.cost


def test_ambiguous_and_empty_goal_forms_fail_closed() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        best_first_search(
            graph(),
            0,
            2,
            goal_node_ids={4},
            edge_cost=edge_cost,
            heuristic=lambda _n: 0.0,
        )
    with pytest.raises(ValueError, match="at least one"):
        best_first_search(
            graph(),
            0,
            None,
            goal_node_ids=(),
            edge_cost=edge_cost,
            heuristic=lambda _n: 0.0,
        )


def test_equal_cost_goal_selection_is_deterministic_by_node_id() -> None:
    equal_graph = TinyGraph(
        {
            0: (1, 2),
            1: (0,),
            2: (0,),
        }
    )

    def unit_cost(_a: int, _b: int) -> float:
        return 1.0

    results = [
        best_first_search(
            equal_graph,
            0,
            None,
            goal_node_ids={2, 1},
            edge_cost=unit_cost,
            heuristic=lambda _n: 0.0,
        )
        for _ in range(5)
    ]
    assert {result.selected_goal_node_id for result in results} == {1}
    assert {result.path for result in results} == {(0, 1)}


def test_goal_set_dijkstra_matches_exhaustive_single_goal_oracle() -> None:
    candidate_goals = (2, 4)
    goal_set_result = best_first_search(
        graph(),
        0,
        None,
        goal_node_ids=candidate_goals,
        edge_cost=edge_cost,
        heuristic=lambda _n: 0.0,
    )
    single_goal_results = [
        best_first_search(
            graph(),
            0,
            goal,
            edge_cost=edge_cost,
            heuristic=lambda _n: 0.0,
        )
        for goal in candidate_goals
    ]
    oracle = min(single_goal_results, key=lambda result: (result.cost, result.path[-1]))
    assert goal_set_result.cost == oracle.cost
    assert goal_set_result.selected_goal_node_id == oracle.selected_goal_node_id
    assert goal_set_result.path == oracle.path
