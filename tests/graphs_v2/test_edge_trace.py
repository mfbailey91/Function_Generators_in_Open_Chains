"""Version 2 edge-trace tests (Sprint V2.3, V2-304)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch, gearbox_2d_branch

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.sampling import TransitionParameterization
from inequality_mechanisms.graphs.transitions import build_edge_trace_v2


class TestEdgeTraceInputLinear:
    def test_endpoint_consistency(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(4, 4))
        a, b = 0, 1  # adjacent along the fastest-varying axis
        trace = graph.edge_trace(a, b, n_samples=9)
        assert trace.s[0] == pytest.approx(0.0)
        assert trace.s[-1] == pytest.approx(1.0)
        assert trace.u[0] == pytest.approx(graph.u_state(a))
        assert trace.u[-1] == pytest.approx(graph.u_state(b))
        assert trace.q[0] == pytest.approx(graph.q_state(a), abs=1e-9)
        assert trace.q[-1] == pytest.approx(graph.q_state(b), abs=1e-9)

    def test_interior_consistency_and_validity(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(4, 4))
        trace = graph.edge_trace(0, 1, n_samples=11)
        assert np.all(trace.branch_valid)
        assert trace.first_invalid_index is None
        for k in range(trace.s.shape[0]):
            assert branch.forward(trace.u[k]) == pytest.approx(trace.q[k], abs=1e-9)
        finite = np.isfinite(trace.forward_inverse_residual)
        assert np.all(trace.forward_inverse_residual[finite] <= 1e-6)

    def test_no_wrapping_for_nonlinear_branch(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(7, 7))
        # Pick two neighboring nodes along axis 0.
        a = graph.topology.node_id((2, 3))
        b = graph.topology.node_id((3, 3))
        trace = graph.edge_trace(a, b, n_samples=13)
        assert np.all(trace.branch_valid)
        # u must move monotonically along the straight interpolation (no wrap).
        u_axis0 = trace.u[:, 0]
        diffs = np.diff(u_axis0)
        assert np.all(diffs > 0) or np.all(diffs < 0)


class TestEdgeTraceOutputLinear:
    def test_endpoint_consistency(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(4, 4))
        a, b = 0, 1
        trace = graph.edge_trace(a, b, n_samples=9)
        assert trace.q[0] == pytest.approx(graph.q_state(a))
        assert trace.q[-1] == pytest.approx(graph.q_state(b))
        assert trace.u[0] == pytest.approx(graph.u_state(a), abs=1e-9)
        assert trace.u[-1] == pytest.approx(graph.u_state(b), abs=1e-9)

    def test_interior_consistency_and_validity(self) -> None:
        branch = fourbar_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_output(branch, shape=(7, 7))
        a = graph.topology.node_id((2, 3))
        b = graph.topology.node_id((2, 4))
        trace = graph.edge_trace(a, b, n_samples=13)
        assert np.all(trace.branch_valid)
        assert trace.first_invalid_index is None
        for k in range(trace.s.shape[0]):
            assert branch.inverse(trace.q[k]) == pytest.approx(trace.u[k], abs=1e-6)
        finite = np.isfinite(trace.forward_inverse_residual)
        assert np.all(trace.forward_inverse_residual[finite] <= 1e-5)


class TestEdgeTraceDirectBuilder:
    def test_input_linear_matches_manual_interpolation(self) -> None:
        branch = gearbox_2d_branch()
        u_a = np.array([-0.5, -0.5])
        u_b = np.array([0.5, 0.5])
        q_a = branch.forward(u_a)
        q_b = branch.forward(u_b)
        trace = build_edge_trace_v2(
            branch,
            TransitionParameterization.INPUT_LINEAR,
            q_a,
            u_a,
            q_b,
            u_b,
            n_samples=5,
        )
        expected_u = np.linspace(u_a, u_b, 5)
        assert trace.u == pytest.approx(expected_u)

    def test_output_linear_matches_manual_interpolation(self) -> None:
        branch = gearbox_2d_branch()
        u_a = np.array([-0.5, -0.5])
        u_b = np.array([0.5, 0.5])
        q_a = branch.forward(u_a)
        q_b = branch.forward(u_b)
        trace = build_edge_trace_v2(
            branch,
            TransitionParameterization.OUTPUT_LINEAR,
            q_a,
            u_a,
            q_b,
            u_b,
            n_samples=5,
        )
        expected_q = np.linspace(q_a, q_b, 5)
        assert trace.q == pytest.approx(expected_q)

    def test_n_samples_too_small_rejected(self) -> None:
        branch = gearbox_2d_branch()
        u_a = np.array([-0.5, -0.5])
        u_b = np.array([0.5, 0.5])
        q_a = branch.forward(u_a)
        q_b = branch.forward(u_b)
        with pytest.raises(ValueError, match="n_samples"):
            build_edge_trace_v2(
                branch,
                TransitionParameterization.INPUT_LINEAR,
                q_a,
                u_a,
                q_b,
                u_b,
                n_samples=1,
            )


class TestEdgeTraceGraphErrors:
    def test_out_of_range_node_id_rejected(self) -> None:
        branch = gearbox_2d_branch()
        graph = EmbeddedPlanningGraph.from_uniform_input(branch, shape=(3, 3))
        with pytest.raises(ValueError, match="out of range"):
            graph.edge_trace(0, 999)
