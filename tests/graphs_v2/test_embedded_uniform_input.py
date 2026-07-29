"""Uniform-input sampling tests (Sprint V2.3, V2-302)."""

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

_EPS = 1e-9


class TestUniformInput1DAffine:
    def test_nodes_and_provenance(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(7,))
        assert graph.node_count == 7
        assert graph.topology.wrap == (False,)
        assert graph.sampling_domain is SamplingDomain.INPUT
        expected_param = TransitionParameterization.INPUT_LINEAR
        assert graph.transition_parameterization is expected_param
        assert np.all(graph.valid_nodes)

    def test_u_nodes_are_exact_linspace(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(11,))
        expected = np.linspace(0.0, 10.0, 11)
        assert graph.u_nodes[:, 0] == pytest.approx(expected)
        # q = u for the unit gearbox, so uniform-U implies uniform-Q here.
        assert graph.q_nodes[:, 0] == pytest.approx(expected)

    def test_uniformity_in_sampled_domain(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(9,))
        stats = graph.output_axis_spacing(0)
        assert stats.max_to_min_ratio == pytest.approx(1.0, abs=1e-9)

    def test_forward_map_residual(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(5,))
        for node_id in range(graph.node_count):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            assert np.max(np.abs(branch.forward(u) - q)) <= _EPS

    def test_nonperiodic_boundary_degree(self) -> None:
        branch = affine_1d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(6,))
        assert graph.neighbors(0) == (1,)
        assert graph.neighbors(5) == (4,)
        assert graph.neighbors(2) == (1, 3)


class TestUniformInput2DGearbox:
    def test_shape_and_provenance(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(5, 5))
        assert graph.node_count == 25
        assert graph.topology.wrap == (False, False)
        assert graph.q_nodes.shape == (25, 2)
        assert graph.u_nodes.shape == (25, 2)
        assert np.all(graph.valid_nodes)

    def test_uniform_in_both_domains(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(6, 8))
        for axis in range(2):
            stats = graph.output_axis_spacing(axis)
            assert stats.max_to_min_ratio == pytest.approx(1.0, abs=1e-8)

    def test_round_trip_node_invariants(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(4, 4))
        for node_id in range(graph.node_count):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            u_back = branch.inverse(q)
            assert u_back == pytest.approx(u, abs=1e-9)

    def test_satisfies_search_graph_protocol(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(3, 3))
        assert isinstance(graph, SearchGraph)


class TestUniformInput2DFourBar:
    def test_uniform_u_maps_to_nonuniform_q(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(15, 15))
        # U is uniform by construction.
        for axis in range(2):
            u_stats = graph.actuator_axis_spacing(axis)
            assert u_stats.max_to_min_ratio == pytest.approx(1.0, abs=1e-8)
        # Q is not: the four-bar map is nonlinear, so mapped output spacing
        # must show measurable nonuniformity evidence.
        found_nonuniform = False
        for axis in range(2):
            q_stats = graph.output_axis_spacing(axis)
            if q_stats.max_to_min_ratio > 1.05:
                found_nonuniform = True
        assert found_nonuniform

    def test_all_nodes_valid_and_within_branch(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(9, 9))
        assert np.all(graph.valid_nodes)
        for node_id in range(graph.node_count):
            u = graph.u_state(node_id)
            q = graph.q_state(node_id)
            assert branch.contains_input(u)
            assert branch.contains_output(q)

    def test_round_trip_node_invariants(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(7, 7))
        for node_id in range(graph.node_count):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            u_back = branch.inverse(q)
            assert u_back == pytest.approx(u, abs=1e-6)

    def test_forward_map_residual_within_epsilon(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(6, 6))
        for node_id in range(graph.node_count):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            assert np.max(np.abs(branch.forward(u) - q)) <= 1e-6


class TestUniformInputErrors:
    def test_shape_dimension_mismatch_rejected(self) -> None:
        branch = affine_1d_branch()
        with pytest.raises(ValueError, match="length 1"):
            EmbeddedPlanningGraph.from_uniform_input(branch, shape=(3, 3))
