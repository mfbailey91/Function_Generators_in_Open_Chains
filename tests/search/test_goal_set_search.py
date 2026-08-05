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
