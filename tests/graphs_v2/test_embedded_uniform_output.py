"""Uniform-output sampling tests (Sprint V2.3, V2-303)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import (
    affine_1d_branch,
    fourbar_2d_branch,
    gearbox_2d_branch,
)

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.sampling import (
    SamplingDomain,
    TransitionParameterization,
)
from inequality_mechanisms.search.protocol import SearchGraph


class TestUniformOutput1DAffine:
    def test_nodes_and_provenance(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(7,))
        assert graph.node_count == 7
        assert graph.topology.wrap == (False,)
        assert graph.sampling_domain is SamplingDomain.OUTPUT
        expected_param = TransitionParameterization.OUTPUT_LINEAR
        assert graph.transition_parameterization is expected_param
        assert np.all(graph.valid_nodes)

    def test_q_nodes_are_exact_linspace(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(11,))
        expected = np.linspace(0.0, 10.0, 11)
        assert graph.q_nodes[:, 0] == pytest.approx(expected)
        assert graph.u_nodes[:, 0] == pytest.approx(expected)

    def test_uniformity_in_sampled_domain(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(9,))
        stats = graph.actuator_axis_spacing(0)
        assert stats.max_to_min_ratio == pytest.approx(1.0, abs=1e-9)


class TestUniformOutput2DGearbox:
    def test_uniform_in_both_domains(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(6, 8))
        for axis in range(2):
            stats = graph.actuator_axis_spacing(axis)
            assert stats.max_to_min_ratio == pytest.approx(1.0, abs=1e-8)

    def test_round_trip_node_invariants(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(4, 4))
        for node_id in range(graph.node_count):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            assert branch.forward(u) == pytest.approx(q, abs=1e-9)

    def test_satisfies_search_graph_protocol(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(3, 3))
        assert isinstance(graph, SearchGraph)


class TestUniformOutput2DFourBar:
    def test_uniform_q_maps_to_nonuniform_u(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(15, 15))
        # Q is uniform by construction.
        for axis in range(2):
            q_stats = graph.output_axis_spacing(axis)
            assert q_stats.max_to_min_ratio == pytest.approx(1.0, abs=1e-8)
        # U is not: the four-bar inverse is nonlinear, so mapped actuator
        # spacing must show measurable nonuniformity evidence.
        found_nonuniform = False
        for axis in range(2):
            u_stats = graph.actuator_axis_spacing(axis)
            if u_stats.max_to_min_ratio > 1.05:
                found_nonuniform = True
        assert found_nonuniform

    def test_all_nodes_valid_and_within_branch(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(9, 9))
        assert np.all(graph.valid_nodes)
        for node_id in range(graph.node_count):
            u = graph.u_state(node_id)
            q = graph.q_state(node_id)
            assert branch.contains_input(u)
            assert branch.contains_output(q)

    def test_round_trip_node_invariants(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(7, 7))
        for node_id in range(graph.node_count):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            assert branch.forward(u) == pytest.approx(q, abs=1e-6)


class TestUniformOutputErrors:
    def test_shape_dimension_mismatch_rejected(self) -> None:
        branch = affine_1d_branch()
        with pytest.raises(ValueError, match="length 1"):
            EmbeddedPlanningGraph.from_uniform_output(branch, shape=(3, 3))
