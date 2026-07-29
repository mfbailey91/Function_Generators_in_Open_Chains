"""Tests for monotonic uniform-Q lattice (S4-11b)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.experiments.sprint4_qgrid import build_monotonic_control_graphs
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.output_grid import MonotonicOutputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.monotonic import monotonic_box_for_independent_fourbars
from inequality_mechanisms.search.dijkstra import dijkstra
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.spaces.output_space import OutputSpace

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


def _mech() -> IndependentFourBars:
    return IndependentFourBars(
        [
            PlanarFourBar(**_CRANK_ROCKER, branch=1, periodic=(False,), name="b0"),
            PlanarFourBar(**_CRANK_ROCKER, branch=1, periodic=(False,), name="b1"),
        ]
    )


class TestMonotonicOutputGraph:
    def test_rejects_periodic_wrap(self) -> None:
        mech = _mech()
        box = monotonic_box_for_independent_fourbars(mech)
        limits = OutputJointLimits.box(
            lower=[box.q_ranges[0][0], box.q_ranges[1][0]],
            upper=[box.q_ranges[0][1], box.q_ranges[1][1]],
        )
        grid = PeriodicGrid2D(shape=(6, 6), ranges=box.q_ranges, wrap=(True, False))
        with pytest.raises(ValueError, match="wrap"):
            MonotonicOutputGraph(
                grid,
                mech,
                limits,
                u_ranges=box.u_ranges,
                edge_samples=5,
                output_space=OutputSpace.from_limits(limits),
            )

    def test_valid_nodes_have_unique_attached_u(self) -> None:
        pack = build_monotonic_control_graphs(_mech(), shape=(8, 8), edge_samples=5)
        q_graph: MonotonicOutputGraph = pack["q_graph"]
        assert q_graph.valid_node_count >= 4
        for node in q_graph.iter_valid_nodes():
            u = q_graph.attached_u(node.node_id)
            assert u.shape == (2,)
            assert np.all(np.isfinite(u))
            q = np.asarray(node.coordinates, dtype=np.float64)
            q_fwd = q_graph.output_space.canonicalize(
                q_graph.mechanism.input_to_output(u)
            )
            assert float(np.linalg.norm(q_fwd - q_graph.output(q))) < 1e-4

    def test_search_finds_path_on_q_grid(self) -> None:
        pack = build_monotonic_control_graphs(_mech(), shape=(8, 8), edge_samples=5)
        q_graph: MonotonicOutputGraph = pack["q_graph"]
        nodes = list(q_graph.iter_valid_nodes())
        start = nodes[0].node_id
        goal = nodes[-1].node_id
        result = dijkstra(q_graph, start, goal)  # type: ignore[arg-type]
        assert result.found
        assert result.path[0] == start
        assert result.path[-1] == goal


class TestMatchedControlGraphs:
    def test_u_and_q_share_limits_and_open_wrap(self) -> None:
        pack = build_monotonic_control_graphs(_mech(), shape=(8, 8), edge_samples=5)
        u_graph = pack["u_graph"]
        q_graph = pack["q_graph"]
        assert u_graph.grid.wrap == (False, False)
        assert q_graph.grid.wrap == (False, False)
        np.testing.assert_allclose(u_graph.limits.lower, q_graph.limits.lower)
        np.testing.assert_allclose(u_graph.limits.upper, q_graph.limits.upper)
        assert u_graph.valid_node_count >= 2
        assert q_graph.valid_node_count >= 2
