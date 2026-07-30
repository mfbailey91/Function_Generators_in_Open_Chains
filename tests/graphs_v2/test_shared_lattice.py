"""Shared uniform-Q null-control graph invariants (Sprint V2.3, V2-306/V2-308)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch


def _matched_branches():
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar)
    return fourbar, gearbox


class TestSharedUniformOutputLattice:
    def test_lattice_built_once_and_reused(self) -> None:
        fourbar, gearbox = _matched_branches()
        shared = UniformOutputLattice.from_output_space(
            fourbar.output_space, shape=(9, 9)
        )
        g_fourbar = EmbeddedPlanningGraph.from_output_lattice(shared, fourbar)
        g_gearbox = EmbeddedPlanningGraph.from_output_lattice(shared, gearbox)

        # Identical topology.
        assert g_fourbar.topology is g_gearbox.topology
        assert g_fourbar.topology.shape == g_gearbox.topology.shape
        assert g_fourbar.topology.wrap == g_gearbox.topology.wrap

        # Bitwise-identical q_nodes: never independently regenerated.
        assert np.array_equal(g_fourbar.q_nodes, g_gearbox.q_nodes)
        assert np.array_equal(g_fourbar.q_nodes, shared.q_nodes)

        # Identical validity masks.
        assert np.array_equal(g_fourbar.valid_nodes, g_gearbox.valid_nodes)
        assert np.all(g_fourbar.valid_nodes)

        # Identical neighbor lists for every node.
        for node_id in range(g_fourbar.node_count):
            assert g_fourbar.neighbors(node_id) == g_gearbox.neighbors(node_id)

        # Identical output edge distances (trivial given identical q_nodes,
        # but asserted explicitly per the sprint's null-control contract).
        for a, b in g_fourbar.topology.iter_edges():
            q_fb_a, q_fb_b = g_fourbar.q_state(a), g_fourbar.q_state(b)
            q_gb_a, q_gb_b = g_gearbox.q_state(a), g_gearbox.q_state(b)
            dist_fourbar = float(np.linalg.norm(q_fb_a - q_fb_b))
            dist_gearbox = float(np.linalg.norm(q_gb_a - q_gb_b))
            assert dist_fourbar == pytest.approx(dist_gearbox, abs=1e-12)

    def test_actuator_realizations_differ_between_mechanisms(self) -> None:
        """The null control varies U per mechanism while holding Q fixed."""
        fourbar, gearbox = _matched_branches()
        shared = UniformOutputLattice.from_output_space(
            fourbar.output_space, shape=(9, 9)
        )
        g_fourbar = EmbeddedPlanningGraph.from_output_lattice(shared, fourbar)
        g_gearbox = EmbeddedPlanningGraph.from_output_lattice(shared, gearbox)
        assert not np.allclose(g_fourbar.u_nodes, g_gearbox.u_nodes)

    def test_round_trip_consistency_per_mechanism(self) -> None:
        fourbar, gearbox = _matched_branches()
        shared = UniformOutputLattice.from_output_space(
            fourbar.output_space, shape=(7, 7)
        )
        for branch in (fourbar, gearbox):
            graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
            for node_id in range(graph.node_count):
                q = graph.q_state(node_id)
                u = graph.u_state(node_id)
                assert branch.forward(u) == pytest.approx(q, abs=1e-6)

    def test_output_dim_mismatch_rejected(self) -> None:
        fourbar, _ = _matched_branches()
        shared = UniformOutputLattice.from_output_space(
            fourbar.output_space, shape=(5, 5)
        )
        from inequality_mechanisms.mechanisms import unit_gearbox_branch

        mismatched = unit_gearbox_branch(1, input_lower=[0.0], input_upper=[1.0])
        with pytest.raises(ValueError, match="output_dim"):
            EmbeddedPlanningGraph.from_output_lattice(shared, mismatched)
