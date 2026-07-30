"""Shared-Q pair invariant regression tests (Sprint V2.8, V2-802)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.graphs.pair_invariants import (
    SharedQPairInvariantError,
    assert_shared_q_pair_invariants,
)
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch


def _paired_graphs(shape: tuple[int, int] = (7, 7)):
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(fourbar.output_space, shape=shape)
    g_fb = EmbeddedPlanningGraph.from_output_lattice(shared, fourbar)
    g_gb = EmbeddedPlanningGraph.from_output_lattice(shared, gearbox)
    return g_fb, g_gb


class TestSharedQPairInvariants:
    def test_matched_pair_passes(self) -> None:
        g_fb, g_gb = _paired_graphs()
        report = assert_shared_q_pair_invariants(g_fb, g_gb, raise_on_failure=True)
        assert report.passed
        assert report.failures == ()
        assert report.details["n_checked_nodes"] > 0

    def test_validity_mismatch_fails(self) -> None:
        g_fb, g_gb = _paired_graphs(shape=(5, 5))
        broken_valid = g_gb.valid_nodes.copy()
        assert bool(broken_valid[0])
        broken_valid[0] = False
        g_broken = replace(g_gb, valid_nodes=broken_valid)
        with pytest.raises(SharedQPairInvariantError, match="valid_nodes"):
            assert_shared_q_pair_invariants(g_fb, g_broken, raise_on_failure=True)

    def test_report_without_raise(self) -> None:
        g_fb, g_gb = _paired_graphs(shape=(5, 5))
        broken_valid = g_gb.valid_nodes.copy()
        broken_valid[0] = False
        g_broken = replace(g_gb, valid_nodes=broken_valid)
        report = assert_shared_q_pair_invariants(g_fb, g_broken, raise_on_failure=False)
        assert report.passed is False
        assert report.failures
        assert isinstance(report.to_dict()["failures"], list)
