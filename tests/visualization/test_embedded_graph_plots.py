"""Smoke tests for Version 2 embedded-graph diagnostics (Sprint V2.3, V2-307)."""

from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    fixed_ratio_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.visualization.embedded_graphs import (
    plot_actuator_samples,
    plot_axis_mapping,
    plot_edge_trace,
    plot_output_graph,
    plot_sampling_mode_comparison,
    plot_spacing_statistics,
)

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


def _fourbar_branch():
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


class TestEmbeddedGraphDiagnostics:
    def test_actuator_and_output_graph_plots(self, tmp_path: Path) -> None:
        branch = fixed_ratio_gearbox_branch(
            [1.5, -0.5], input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(6, 6))
        out_u = plot_actuator_samples(graph, tmp_path / "u.png")
        out_q = plot_output_graph(graph, tmp_path / "q.png")
        assert out_u.is_file() and out_u.stat().st_size > 0
        assert out_q.is_file() and out_q.stat().st_size > 0

    def test_axis_mapping_and_spacing_plots(self, tmp_path: Path) -> None:
        branch = _fourbar_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(9, 9))
        out_map = plot_axis_mapping(graph, 0, tmp_path / "map0.png")
        out_spacing = plot_spacing_statistics(graph, tmp_path / "spacing.png")
        assert out_map.is_file() and out_map.stat().st_size > 0
        assert out_spacing.is_file() and out_spacing.stat().st_size > 0

    def test_sampling_mode_comparison(self, tmp_path: Path) -> None:
        branch = _fourbar_branch()
        input_graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(9, 9))
        output_graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(9, 9))
        out = plot_sampling_mode_comparison(
            input_graph, output_graph, tmp_path / "cmp.png"
        )
        assert out.is_file() and out.stat().st_size > 0

    def test_edge_trace_plot(self, tmp_path: Path) -> None:
        branch = _fourbar_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(7, 7))
        trace = graph.edge_trace(0, 1, n_samples=11)
        out = plot_edge_trace(trace, tmp_path / "trace.png")
        assert out.is_file() and out.stat().st_size > 0

    def test_1d_graph_plots(self, tmp_path: Path) -> None:
        branch = fixed_ratio_gearbox_branch([2.0], input_lower=[0.0], input_upper=[1.0])
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(8,))
        out_u = plot_actuator_samples(graph, tmp_path / "u1d.png")
        out_q = plot_output_graph(graph, tmp_path / "q1d.png")
        assert out_u.is_file() and out_u.stat().st_size > 0
        assert out_q.is_file() and out_q.stat().st_size > 0
