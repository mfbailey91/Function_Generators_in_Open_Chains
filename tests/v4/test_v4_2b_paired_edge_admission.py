"""V4.2B: one final paired search topology after connector evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from inequality_mechanisms.search.core import best_first_search


@dataclass
class TinyGraph:
    """Minimal SearchGraph with explicit adjacency."""

    _node_count: int
    _adj: dict[int, tuple[int, ...]]

    @property
    def node_count(self) -> int:
        return self._node_count

    def node_is_valid(self, node_id: int) -> bool:
        return 0 <= int(node_id) < self._node_count

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        return self._adj.get(int(node_id), ())


TRIANGLE = TinyGraph(3, {0: (1, 2), 1: (2,), 2: ()})
PAIR = TinyGraph(2, {0: (1,), 1: ()})


def _compile(graph: TinyGraph, costs: dict[str, object]):
    from inequality_mechanisms.graphs.paired_edge_admission import (
        compile_paired_finite_neighbors,
    )

    return compile_paired_finite_neighbors(graph, costs)


def test_both_available_admits_one_common_edge() -> None:
    compiled = _compile(
        PAIR,
        {
            "fourbar": lambda _u, _v: 1.0,
            "gearbox": lambda _u, _v: 2.5,
        },
    )
    assert compiled.admitted_edge_ids == ((0, 1),)
    assert compiled.rejected_candidates == {}
    assert tuple(compiled.graph.neighbors(0)) == (1,)
    assert compiled.edge_costs["fourbar"](0, 1) == pytest.approx(1.0)
    assert compiled.edge_costs["gearbox"](0, 1) == pytest.approx(2.5)


def test_both_unavailable_omits_edge() -> None:
    compiled = _compile(
        PAIR,
        {
            "fourbar": lambda _u, _v: math.inf,
            "gearbox": lambda _u, _v: math.inf,
        },
    )
    assert compiled.admitted_edge_ids == ()
    record = compiled.rejected_candidates[(0, 1)]
    assert record["fourbar"].candidate_edge_status == "unavailable_local_motion"
    assert record["gearbox"].candidate_edge_status == "unavailable_local_motion"
    assert 1 not in tuple(compiled.graph.neighbors(0))


def test_one_available_one_unavailable_omits_for_both() -> None:
    compiled = _compile(
        PAIR,
        {
            "fourbar": lambda _u, _v: 1.0,
            "gearbox": lambda _u, _v: math.inf,
        },
    )
    assert compiled.admitted_edge_ids == ()
    record = compiled.rejected_candidates[(0, 1)]
    assert record["fourbar"].candidate_edge_status == "available_local_motion"
    assert record["fourbar"].weight == pytest.approx(1.0)
    assert record["gearbox"].candidate_edge_status == "unavailable_local_motion"
    assert 1 not in tuple(compiled.graph.neighbors(0))
    with pytest.raises(ValueError, match="not an admitted"):
        compiled.edge_costs["fourbar"](0, 1)


@pytest.mark.parametrize(
    "bad",
    [math.nan, -math.inf, -1.0],
)
@pytest.mark.parametrize("bad_arm", ["fourbar", "gearbox"])
def test_invalid_numeric_in_either_arm_raises(bad: float, bad_arm: str) -> None:
    costs = {
        "fourbar": lambda _u, _v: 1.0,
        "gearbox": lambda _u, _v: 1.0,
    }
    costs[bad_arm] = lambda _u, _v: bad
    with pytest.raises(ValueError, match="NaN|negative"):
        _compile(PAIR, costs)


def test_all_unavailable_returns_found_false() -> None:
    compiled = _compile(
        PAIR,
        {
            "fourbar": lambda _u, _v: math.inf,
            "gearbox": lambda _u, _v: math.inf,
        },
    )
    result = best_first_search(
        compiled.graph,
        0,
        1,
        edge_cost=compiled.edge_costs["fourbar"],
        heuristic=lambda _node: 0.0,
    )
    assert result.found is False
    assert result.selected_goal_node_id is None


def test_disconnected_remainder_is_still_searchable() -> None:
    def fourbar(u: int, v: int) -> float:
        return 1.0

    def gearbox(u: int, v: int) -> float:
        if (u, v) == (1, 2):
            return math.inf
        return 1.0

    compiled = _compile(TRIANGLE, {"fourbar": fourbar, "gearbox": gearbox})
    assert (0, 1) in compiled.admitted_edge_ids
    assert (0, 2) in compiled.admitted_edge_ids
    assert (1, 2) not in compiled.admitted_edge_ids
    reachable = best_first_search(
        compiled.graph,
        0,
        1,
        edge_cost=compiled.edge_costs["fourbar"],
        heuristic=lambda _node: 0.0,
    )
    unreachable = best_first_search(
        compiled.graph,
        1,
        2,
        edge_cost=compiled.edge_costs["fourbar"],
        heuristic=lambda _node: 0.0,
    )
    assert reachable.found is True
    assert unreachable.found is False


def test_admitted_ids_and_digests_are_deterministic() -> None:
    def fourbar(u: int, v: int) -> float:
        if (u, v) == (0, 2):
            return math.inf
        return 1.0

    def gearbox(u: int, v: int) -> float:
        return 2.0

    first = _compile(TRIANGLE, {"fourbar": fourbar, "gearbox": gearbox})
    second = _compile(TRIANGLE, {"fourbar": fourbar, "gearbox": gearbox})
    assert first.candidate_edge_ids == second.candidate_edge_ids == ((0, 1), (0, 2), (1, 2))
    assert first.admitted_edge_ids == second.admitted_edge_ids == ((0, 1), (1, 2))
    assert first.candidate_topology_digest == second.candidate_topology_digest
    assert first.admitted_topology_digest == second.admitted_topology_digest
    assert first.candidate_topology_digest != first.admitted_topology_digest


def test_dijkstra_astar_parity_on_common_graph() -> None:
    def fourbar(u: int, v: int) -> float:
        if (u, v) == (0, 2):
            return math.inf
        return 1.0

    def gearbox(u: int, v: int) -> float:
        if (u, v) == (0, 2):
            return 0.5
        return 1.0

    compiled = _compile(TRIANGLE, {"fourbar": fourbar, "gearbox": gearbox})
    dijkstra = best_first_search(
        compiled.graph,
        0,
        2,
        edge_cost=compiled.edge_costs["fourbar"],
        heuristic=lambda _node: 0.0,
    )
    astar = best_first_search(
        compiled.graph,
        0,
        2,
        edge_cost=compiled.edge_costs["fourbar"],
        heuristic=lambda node: float(abs(2 - node)),
    )
    assert dijkstra.found is True
    assert astar.found is True
    assert dijkstra.cost == pytest.approx(astar.cost)
    assert dijkstra.cost == pytest.approx(2.0)
    assert 2 not in tuple(compiled.graph.neighbors(0))


def test_compile_paired_q_search_graph_requires_matching_keys() -> None:
    from inequality_mechanisms.graphs.paired_edge_admission import (
        compile_paired_q_search_graph,
    )
    from inequality_mechanisms.graphs.paired_q_planning import (
        build_paired_q_planning_graph,
    )
    from inequality_mechanisms.mechanisms.operating_branch import unit_gearbox_branch

    fourbar = unit_gearbox_branch(
        2, input_lower=[-0.5, -0.5], input_upper=[0.5, 0.5], name="fourbar"
    )
    gearbox = unit_gearbox_branch(
        2, input_lower=[-0.5, -0.5], input_upper=[0.5, 0.5], name="gearbox"
    )
    paired = build_paired_q_planning_graph(
        {"fourbar": fourbar, "gearbox": gearbox},
        q_shape=(3, 3),
    )
    with pytest.raises(ValueError, match="must match paired arms"):
        compile_paired_q_search_graph(
            paired,
            {"fourbar": lambda _u, _v: 1.0},
        )
