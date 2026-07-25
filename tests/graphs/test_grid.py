"""Tests for periodic four-connected 2-D input grids."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.graphs import PeriodicGrid2D


class TestPeriodicGrid2D:
    def test_deterministic_indexing(self) -> None:
        grid = PeriodicGrid2D((4, 5), wrap=(False, False))
        assert grid.node_count == 20
        assert grid.node_id(0, 0) == 0
        assert grid.node_id(0, 4) == 4
        assert grid.node_id(1, 0) == 5
        assert grid.node_id(3, 4) == 19
        assert grid.indices_from_id(17) == (3, 2)

    def test_coordinates_exclude_upper_endpoint(self) -> None:
        grid = PeriodicGrid2D(
            (4, 4),
            ranges=((0.0, 2.0 * np.pi), (0.0, 2.0 * np.pi)),
            wrap=(True, True),
        )
        assert grid.coordinates(0, 0) == pytest.approx((0.0, 0.0))
        u0, u1 = grid.coordinates(3, 3)
        assert u0 == pytest.approx(1.5 * np.pi)
        assert u1 == pytest.approx(1.5 * np.pi)
        # Upper bound itself is not a sample (avoids double-counting 0 and 2pi).
        coords = grid.coordinate_array()
        assert not np.any(np.isclose(coords[:, 0], 2.0 * np.pi))

    def test_four_connectivity_no_wrap_corner(self) -> None:
        grid = PeriodicGrid2D((3, 3), wrap=(False, False))
        assert grid.neighbors(0, 0) == [(1, 0), (0, 1)]
        assert grid.neighbors(1, 1) == [(2, 1), (0, 1), (1, 2), (1, 0)]
        assert grid.neighbors(2, 2) == [(1, 2), (2, 1)]

    def test_wrapping_connects_boundaries(self) -> None:
        grid = PeriodicGrid2D((4, 4), wrap=(True, True))
        nbs = set(grid.neighbors(0, 0))
        assert (3, 0) in nbs  # wrap axis 0
        assert (0, 3) in nbs  # wrap axis 1
        assert len(grid.neighbors(0, 0)) == 4
        assert len(grid.neighbors(2, 2)) == 4

    def test_partial_wrap(self) -> None:
        grid = PeriodicGrid2D((4, 4), wrap=(True, False))
        nbs = set(grid.neighbors(0, 0))
        assert (3, 0) in nbs
        assert (0, 3) not in nbs
        assert (0, 1) in nbs

    def test_undirected_edge_count_torus(self) -> None:
        n0, n1 = 5, 6
        grid = PeriodicGrid2D((n0, n1), wrap=(True, True))
        edges = list(grid.iter_edges())
        assert len(edges) == 2 * n0 * n1
        assert all(a < b for a, b in edges)

    def test_undirected_edge_count_open(self) -> None:
        n0, n1 = 4, 5
        grid = PeriodicGrid2D((n0, n1), wrap=(False, False))
        edges = list(grid.iter_edges())
        expected = n0 * (n1 - 1) + n1 * (n0 - 1)
        assert len(edges) == expected

    def test_invalid_shape_rejected(self) -> None:
        with pytest.raises(ValueError, match=">= 2"):
            PeriodicGrid2D((1, 4))

    def test_out_of_range_indices(self) -> None:
        grid = PeriodicGrid2D((3, 3), wrap=(False, False))
        with pytest.raises(ValueError, match="out of range"):
            grid.node_id(0, 3)

    def test_networkx_validation_graph(self) -> None:
        nx = pytest.importorskip("networkx")
        grid = PeriodicGrid2D((4, 4), wrap=(True, True))
        g = grid.to_networkx()
        assert g.number_of_nodes() == 16
        assert g.number_of_edges() == 32
        assert nx.is_connected(g)
        # Every node degree is 4 on a toroidal four-connected lattice.
        assert all(deg == 4 for _, deg in g.degree())
