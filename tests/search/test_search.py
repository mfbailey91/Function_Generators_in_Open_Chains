"""Tests for Dijkstra and A* on constrained input graphs."""

from __future__ import annotations

import math
from collections import deque

import numpy as np
import pytest

from inequality_mechanisms.graphs import (
    ConstrainedInputGraph,
    PeriodicGrid2D,
    output_euclidean_cost,
)
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.search import (
    astar,
    dijkstra,
    output_euclidean_heuristic,
    reverse_dijkstra,
)
from inequality_mechanisms.search.core import _cached_outputs
from inequality_mechanisms.spaces import OutputJointLimits, OutputSpace

_CR_LENGTHS = (1.0, 2.5, 2.0, 2.0)


def _unit_box_graph(
    shape: tuple[int, int] = (8, 8),
    *,
    wrap: tuple[bool, bool] = (False, False),
    upper: float = 2.0 * np.pi,
) -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(
        shape,
        ranges=((0.0, upper), (0.0, upper)),
        wrap=wrap,
    )
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[upper, upper])
    return ConstrainedInputGraph(grid, mech, limits)


class TestDijkstra:
    def test_manhattan_cost_on_unit_gearbox(self) -> None:
        graph = _unit_box_graph((6, 6), upper=6.0)
        # Coordinates are integer-ish: step = 1.0
        start = graph.grid.node_id(1, 1)
        goal = graph.grid.node_id(4, 2)
        result = dijkstra(graph, start, goal)
        assert result.found is True
        # Axis-aligned unit steps: Manhattan |3| + |1| = 4
        assert result.cost == pytest.approx(4.0)
        assert result.path[0] == start
        assert result.path[-1] == goal
        assert result.n_path_edges == len(result.path) - 1
        assert result.n_expanded >= 1
        assert result.n_generated >= 1

    def test_start_equals_goal(self) -> None:
        graph = _unit_box_graph((4, 4), upper=4.0)
        node = graph.grid.node_id(1, 2)
        result = dijkstra(graph, node, node)
        assert result.found is True
        assert result.cost == pytest.approx(0.0)
        assert result.path == (node,)
        assert result.n_expanded == 1
        assert result.n_path_edges == 0

    def test_unreachable_returns_not_found(self) -> None:
        # Two disconnected valid islands under tight limits.
        grid = PeriodicGrid2D(
            (6, 3),
            ranges=((0.0, 6.0), (0.0, 3.0)),
            wrap=(False, False),
        )
        mech = UnitGearbox(dim=2)
        # Only u0 in [0, 1.5] is valid — right side of the grid is cut off.
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.5, 3.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        start = graph.grid.node_id(0, 1)
        # Goal at i0=5 is outside limits → invalid node raises.
        with pytest.raises(ValueError, match="not valid"):
            dijkstra(graph, start, graph.grid.node_id(5, 1))

    def test_invalid_start_rejected(self) -> None:
        graph = _unit_box_graph((4, 4), upper=2.0)
        # Push limits so a corner becomes invalid, then try to start there
        # by building a tighter graph.
        grid = graph.grid
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        tight = ConstrainedInputGraph(grid, mech, limits)
        bad = tight.grid.node_id(3, 3)
        assert tight.node_is_valid_id(bad) is False
        with pytest.raises(ValueError, match="not valid"):
            dijkstra(tight, bad, tight.grid.node_id(0, 0))

    def test_stale_entries_not_counted_as_expansions(self) -> None:
        graph = _unit_box_graph((5, 5), upper=5.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(4, 4)

        # First hop to (1,0) is costly; a longer lattice path improves it.
        # The obsolete heap entry (g=5) is popped before the goal (g*=8) and
        # must be counted as stale, not as a second expansion.
        def edge_cost(u: int, v: int) -> float:
            iu = graph.grid.indices_from_id(u)
            iv = graph.grid.indices_from_id(v)
            if sorted([iu, iv]) == [(0, 0), (1, 0)]:
                return 5.0
            return 1.0

        result = dijkstra(graph, start, goal, edge_cost=edge_cost)
        assert result.found is True
        assert result.cost == pytest.approx(8.0)
        assert result.n_stale >= 1
        assert result.n_expanded <= graph.valid_node_count

    def test_deterministic_path(self) -> None:
        graph = _unit_box_graph((6, 6), upper=6.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(3, 3)
        a = dijkstra(graph, start, goal)
        b = dijkstra(graph, start, goal)
        assert a.path == b.path
        assert a.cost == b.cost
        assert a.n_expanded == b.n_expanded


class TestAStar:
    def test_matches_dijkstra_cost_unit_gearbox(self) -> None:
        graph = _unit_box_graph((10, 10), upper=10.0)
        start = graph.grid.node_id(1, 2)
        goal = graph.grid.node_id(7, 5)
        d = dijkstra(graph, start, goal)
        a = astar(graph, start, goal)
        assert d.found and a.found
        assert a.cost == pytest.approx(d.cost)
        assert a.path[0] == start and a.path[-1] == goal

    def test_matches_dijkstra_on_connected_fourbar_component(self) -> None:
        grid = PeriodicGrid2D((16, 16), wrap=(True, True))
        mech = IndependentFourBars.from_lengths([_CR_LENGTHS, _CR_LENGTHS], branch=1)
        limits = OutputJointLimits.box(lower=[1.05, 1.05], upper=[2.2, 2.2])
        graph = ConstrainedInputGraph(grid, mech, limits)
        valid_ids = [n.node_id for n in graph.iter_valid_nodes()]
        assert len(valid_ids) >= 2

        seen: set[int] = set()
        component: list[int] = []
        seed = valid_ids[0]
        queue: deque[int] = deque([seed])
        seen.add(seed)
        while queue:
            u = queue.popleft()
            component.append(u)
            i0, i1 = graph.grid.indices_from_id(u)
            for j0, j1 in graph.neighbors(i0, i1):
                v = graph.grid.node_id(j0, j1)
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        assert len(component) >= 2
        start, goal = component[0], component[len(component) // 2]
        d = dijkstra(graph, start, goal)
        a = astar(graph, start, goal)
        assert d.found and a.found
        assert a.cost == pytest.approx(d.cost, rel=0.0, abs=1e-12)

    def test_heuristic_zero_at_goal(self) -> None:
        graph = _unit_box_graph((5, 5), upper=5.0)
        goal = graph.grid.node_id(2, 2)
        result = astar(graph, goal, goal)
        assert result.cost == pytest.approx(0.0)
        assert result.n_expanded == 1

    def test_expansions_not_greater_than_dijkstra_typically(self) -> None:
        # Admissible A* should expand no more than Dijkstra on this instance
        # (not a theorem for all graphs with ties, but holds on this grid).
        graph = _unit_box_graph((12, 12), upper=12.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(10, 8)
        d = dijkstra(graph, start, goal)
        a = astar(graph, start, goal)
        assert a.cost == pytest.approx(d.cost)
        assert a.n_expanded <= d.n_expanded

    def test_deterministic_tie_breaking(self) -> None:
        graph = _unit_box_graph((5, 5), upper=5.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(2, 2)
        paths = {astar(graph, start, goal).path for _ in range(5)}
        assert len(paths) == 1


class TestReverseDijkstra:
    def test_cost_to_go_matches_forward_dijkstra(self) -> None:
        graph = _unit_box_graph((8, 8), upper=8.0)
        start = graph.grid.node_id(1, 2)
        goal = graph.grid.node_id(6, 5)
        forward = dijkstra(graph, start, goal)
        ctg = reverse_dijkstra(graph, goal)
        assert forward.found is True
        assert ctg[start] == pytest.approx(forward.cost)
        assert ctg[goal] == pytest.approx(0.0)
        assert ctg.goal == goal

    def test_labels_entire_reachable_component(self) -> None:
        graph = _unit_box_graph((5, 5), upper=5.0)
        goal = graph.grid.node_id(2, 2)
        ctg = reverse_dijkstra(graph, goal)
        assert len(ctg.costs) == graph.valid_node_count
        assert ctg.n_expanded == graph.valid_node_count

    def test_euclidean_heuristic_dominated_by_exact_cost(self) -> None:
        graph = _unit_box_graph((10, 10), upper=10.0)
        goal = graph.grid.node_id(8, 7)
        ctg = reverse_dijkstra(graph, goal)
        output_of = _cached_outputs(graph)
        h = output_euclidean_heuristic(
            graph.mechanism,
            output_of(goal),
            output_of,
            output_space=graph.output_space,
        )
        for node_id, exact in ctg.costs.items():
            assert h(node_id) <= exact + 1e-12

    def test_as_heuristic_recovers_optimal_cost(self) -> None:
        graph = _unit_box_graph((6, 6), upper=6.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(4, 3)
        ctg = reverse_dijkstra(graph, goal)
        forward = dijkstra(graph, start, goal)
        assert ctg.as_heuristic()(start) == pytest.approx(forward.cost)

    def test_invalid_goal_rejected(self) -> None:
        graph = _unit_box_graph((4, 4), upper=2.0)
        grid = graph.grid
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        tight = ConstrainedInputGraph(grid, mech, limits)
        bad = tight.grid.node_id(3, 3)
        assert tight.node_is_valid_id(bad) is False
        with pytest.raises(ValueError, match="not valid"):
            reverse_dijkstra(tight, bad)

    def test_unreachable_query_is_inf(self) -> None:
        grid = PeriodicGrid2D(
            (6, 3),
            ranges=((0.0, 6.0), (0.0, 3.0)),
            wrap=(False, False),
        )
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.5, 3.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        goal = graph.grid.node_id(0, 1)
        ctg = reverse_dijkstra(graph, goal)
        # Node at i0=1 may still be valid; a far invalid id raises on lookup
        # of validity, but absent costs return inf.
        far_valid = [
            n.node_id for n in graph.iter_valid_nodes() if n.node_id not in ctg.costs
        ]
        assert far_valid == []
        assert ctg[999_999] == math.inf


class TestOutputEdgeCost:
    def test_unit_gearbox_matches_input_distance(self) -> None:
        mech = UnitGearbox(dim=2)
        space = OutputSpace.from_limits(
            OutputJointLimits.box(lower=[-10.0, -10.0], upper=[10.0, 10.0])
        )
        c = output_euclidean_cost(
            mech, [0.0, 0.0], [3.0, 4.0], output_space=space
        )
        assert c == pytest.approx(5.0)

    def test_astar_rejects_custom_edge_cost(self) -> None:
        graph = _unit_box_graph((4, 4), upper=4.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(2, 1)

        def edge_cost(u: int, v: int) -> float:
            return 1.0

        with pytest.raises(ValueError, match="custom edge_cost"):
            astar(graph, start, goal, edge_cost=edge_cost)

    def test_networkx_shortest_path_agrees(self) -> None:
        nx = pytest.importorskip("networkx")
        graph = _unit_box_graph((5, 5), upper=5.0)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(3, 1)
        result = dijkstra(graph, start, goal)
        g = graph.to_networkx()
        for u, v in list(g.edges()):
            cu = graph.grid.coordinates(*graph.grid.indices_from_id(u))
            cv = graph.grid.coordinates(*graph.grid.indices_from_id(v))
            g.edges[u, v]["weight"] = output_euclidean_cost(
                graph.mechanism, cu, cv, output_space=graph.output_space
            )
        nx_cost = nx.shortest_path_length(g, start, goal, weight="weight")
        assert result.cost == pytest.approx(nx_cost)
        assert math.isfinite(result.cost)
