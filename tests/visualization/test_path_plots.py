"""Smoke tests for path visualization helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics import Planar2R
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.search import astar
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.visualization.paths import (
    cost_from_start,
    lattice_edge_weights,
    path_inputs,
    path_outputs,
    plot_cartesian_path,
    plot_input_graph_weights,
    plot_input_path,
    plot_output_graph_weights,
    plot_output_path,
)


def _tiny_gearbox_graph() -> ConstrainedInputGraph:
    grid = PeriodicGrid2D(
        (8, 8),
        ranges=((1.0, 2.0), (1.0, 2.0)),
        wrap=(False, False),
    )
    mech = UnitGearbox(dim=2, periodic=(False, False))
    limits = OutputJointLimits(lower=(1.05, 1.05), upper=(1.95, 1.95))
    return ConstrainedInputGraph(grid, mech, limits, edge_samples=5)


class TestPathPlots:
    def test_writes_nonempty_pngs(self, tmp_path: Path) -> None:
        graph = _tiny_gearbox_graph()
        valid = [n.node_id for n in graph.iter_valid_nodes()]
        assert len(valid) >= 2
        start, goal = valid[0], valid[-1]
        result = astar(graph, start, goal)
        assert result.found

        costs = cost_from_start(graph, start)
        u_png = plot_input_path(
            graph,
            result.path,
            tmp_path / "input.png",
            costs=costs,
            start=start,
            goal=goal,
            title="test input",
        )
        q_png = plot_output_path(
            graph,
            result.path,
            tmp_path / "output.png",
            costs=costs,
            start=start,
            goal=goal,
            title="test output",
        )
        x_png = plot_cartesian_path(
            path_outputs(graph, result.path),
            tmp_path / "cartesian.png",
            plant=Planar2R(),
            title="test cartesian",
        )
        for path in (u_png, q_png, x_png):
            assert path.is_file()
            assert path.stat().st_size > 0

    def test_weighted_graph_plots(self, tmp_path: Path) -> None:
        graph = _tiny_gearbox_graph()
        valid = [n.node_id for n in graph.iter_valid_nodes()]
        start, goal = valid[0], valid[-1]
        result = astar(graph, start, goal)
        assert result.found

        edges, u_w, q_w = lattice_edge_weights(graph)
        assert len(edges) == len(u_w) == len(q_w)
        assert len(edges) > 0
        assert np.all(np.isfinite(u_w))
        assert np.all(np.isfinite(q_w))
        assert np.all(u_w > 0)
        assert np.all(q_w > 0)

        u_png = plot_input_graph_weights(
            graph,
            result.path,
            tmp_path / "input_weights.png",
            start=start,
            goal=goal,
            title="weighted U",
        )
        q_png = plot_output_graph_weights(
            graph,
            result.path,
            tmp_path / "output_weights.png",
            start=start,
            goal=goal,
            title="weighted Q",
        )
        for path in (u_png, q_png):
            assert path.is_file()
            assert path.stat().st_size > 0

    def test_path_coordinate_helpers(self) -> None:
        graph = _tiny_gearbox_graph()
        valid = [n.node_id for n in graph.iter_valid_nodes()]
        path = (valid[0], valid[1]) if len(valid) > 1 else (valid[0],)
        u = path_inputs(graph, path)
        q = path_outputs(graph, path)
        assert u.shape == (len(path), 2)
        assert q.shape == (len(path), 2)
        # Unit gearbox: q == u
        assert q == pytest.approx(u)

    def test_cartesian_rejects_bad_shape(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="\\(T, 2\\)"):
            plot_cartesian_path(np.zeros(2), tmp_path / "bad.png")
        with pytest.raises(ValueError, match="at least one"):
            plot_cartesian_path(np.zeros((0, 2)), tmp_path / "empty.png")
