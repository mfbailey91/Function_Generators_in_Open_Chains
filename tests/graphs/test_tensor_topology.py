"""Tests for the coordinate-free N-dimensional ``TensorGridTopology``."""

from __future__ import annotations

import pytest

from inequality_mechanisms.graphs import (
    GraphTopology,
    PeriodicGrid2D,
    TensorGridTopology,
)


class TestTensorGridTopology1D:
    def test_id_round_trip(self) -> None:
        topo = TensorGridTopology((5,))
        assert topo.node_count == 5
        for i in range(5):
            node_id = topo.node_id((i,))
            assert node_id == i
            assert topo.index_from_id(node_id) == (i,)

    def test_boundary_without_wrap(self) -> None:
        topo = TensorGridTopology((5,), wrap=(False,))
        assert topo.neighbors(0) == [1]
        assert topo.neighbors(4) == [3]
        assert topo.neighbors(2) == [1, 3]

    def test_wrap(self) -> None:
        topo = TensorGridTopology((5,), wrap=(True,))
        assert topo.neighbors(0) == [4, 1]
        assert topo.neighbors(4) == [3, 0]

    def test_size_two_wrap_no_duplicate(self) -> None:
        topo = TensorGridTopology((2,), wrap=(True,))
        assert topo.neighbors(0) == [1]
        assert topo.neighbors(1) == [0]

    def test_size_two_no_wrap(self) -> None:
        topo = TensorGridTopology((2,), wrap=(False,))
        assert topo.neighbors(0) == [1]
        assert topo.neighbors(1) == [0]


class TestTensorGridTopology2D:
    def test_id_round_trip_row_major(self) -> None:
        n0, n1 = 4, 5
        topo = TensorGridTopology((n0, n1))
        assert topo.node_count == n0 * n1
        for i0 in range(n0):
            for i1 in range(n1):
                node_id = topo.node_id((i0, i1))
                assert node_id == i0 * n1 + i1
                assert topo.index_from_id(node_id) == (i0, i1)

    def test_matches_periodic_grid_2d_flat_ids_no_wrap(self) -> None:
        n0, n1 = 3, 4
        topo = TensorGridTopology((n0, n1), wrap=(False, False))
        grid = PeriodicGrid2D((n0, n1), wrap=(False, False))
        for i0 in range(n0):
            for i1 in range(n1):
                assert topo.node_id((i0, i1)) == grid.node_id(i0, i1)
                topo_neighbors = {
                    topo.index_from_id(nb)
                    for nb in topo.neighbors(topo.node_id((i0, i1)))
                }
                grid_neighbors = set(grid.neighbors(i0, i1))
                assert topo_neighbors == grid_neighbors

    def test_boundary_without_wrap_corner(self) -> None:
        topo = TensorGridTopology((3, 3), wrap=(False, False))
        corner_neighbors = {
            topo.index_from_id(nb) for nb in topo.neighbors(topo.node_id((0, 0)))
        }
        assert corner_neighbors == {(1, 0), (0, 1)}

    def test_wrap_per_axis(self) -> None:
        topo = TensorGridTopology((4, 4), wrap=(True, False))
        neighbors = {
            topo.index_from_id(nb) for nb in topo.neighbors(topo.node_id((0, 0)))
        }
        assert (3, 0) in neighbors
        assert (0, 3) not in neighbors
        assert (0, 1) in neighbors

    def test_full_wrap_interior_degree_four(self) -> None:
        topo = TensorGridTopology((4, 4), wrap=(True, True))
        assert len(topo.neighbors(topo.node_id((0, 0)))) == 4
        assert len(topo.neighbors(topo.node_id((2, 2)))) == 4

    def test_deterministic_neighbor_order(self) -> None:
        topo = TensorGridTopology((4, 4), wrap=(True, True))
        node_id = topo.node_id((1, 1))
        expected = [
            topo.node_id((0, 1)),
            topo.node_id((2, 1)),
            topo.node_id((1, 0)),
            topo.node_id((1, 2)),
        ]
        assert topo.neighbors(node_id) == expected

    def test_size_two_wrapped_axis_no_duplicate_neighbors(self) -> None:
        topo = TensorGridTopology((2, 3), wrap=(True, False))
        neighbors = topo.neighbors(topo.node_id((0, 1)))
        assert neighbors.count(topo.node_id((1, 1))) == 1

    def test_undirected_edge_count_open(self) -> None:
        n0, n1 = 4, 5
        topo = TensorGridTopology((n0, n1), wrap=(False, False))
        edges = list(topo.iter_edges())
        expected = n0 * (n1 - 1) + n1 * (n0 - 1)
        assert len(edges) == expected
        assert all(a < b for a, b in edges)

    def test_undirected_edge_count_torus(self) -> None:
        n0, n1 = 5, 6
        topo = TensorGridTopology((n0, n1), wrap=(True, True))
        edges = list(topo.iter_edges())
        assert len(edges) == 2 * n0 * n1


class TestTensorGridTopology3D:
    def test_id_round_trip_row_major(self) -> None:
        n0, n1, n2 = 2, 3, 4
        topo = TensorGridTopology((n0, n1, n2))
        assert topo.node_count == n0 * n1 * n2
        for i0 in range(n0):
            for i1 in range(n1):
                for i2 in range(n2):
                    node_id = topo.node_id((i0, i1, i2))
                    assert node_id == (i0 * n1 + i1) * n2 + i2
                    assert topo.index_from_id(node_id) == (i0, i1, i2)

    def test_six_connectivity_interior(self) -> None:
        topo = TensorGridTopology((4, 4, 4), wrap=(False, False, False))
        node_id = topo.node_id((1, 1, 1))
        assert len(topo.neighbors(node_id)) == 6

    def test_boundary_without_wrap_corner(self) -> None:
        topo = TensorGridTopology((3, 3, 3), wrap=(False, False, False))
        corner_neighbors = {
            topo.index_from_id(nb) for nb in topo.neighbors(topo.node_id((0, 0, 0)))
        }
        assert corner_neighbors == {(1, 0, 0), (0, 1, 0), (0, 0, 1)}

    def test_wrap_single_axis(self) -> None:
        topo = TensorGridTopology((3, 3, 3), wrap=(True, False, False))
        neighbors = {
            topo.index_from_id(nb) for nb in topo.neighbors(topo.node_id((0, 0, 0)))
        }
        assert (2, 0, 0) in neighbors
        assert (0, 2, 0) not in neighbors
        assert (0, 0, 2) not in neighbors

    def test_size_two_wrap_no_duplicate_any_axis(self) -> None:
        topo = TensorGridTopology((2, 2, 2), wrap=(True, True, True))
        for node_id in range(topo.node_count):
            neighbors = topo.neighbors(node_id)
            assert len(neighbors) == 3
            assert len(set(neighbors)) == 3

    def test_deterministic_neighbor_order(self) -> None:
        topo = TensorGridTopology((3, 3, 3), wrap=(True, True, True))
        node_id = topo.node_id((1, 1, 1))
        expected = [
            topo.node_id((0, 1, 1)),
            topo.node_id((2, 1, 1)),
            topo.node_id((1, 0, 1)),
            topo.node_id((1, 2, 1)),
            topo.node_id((1, 1, 0)),
            topo.node_id((1, 1, 2)),
        ]
        assert topo.neighbors(node_id) == expected


class TestTensorGridTopologyErrors:
    def test_empty_shape_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one axis"):
            TensorGridTopology(())

    def test_shape_entry_too_small_rejected(self) -> None:
        with pytest.raises(ValueError, match=">= 2"):
            TensorGridTopology((1, 4))

    def test_wrap_length_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="length"):
            TensorGridTopology((3, 3), wrap=(True,))

    def test_node_id_wrong_index_arity_rejected(self) -> None:
        topo = TensorGridTopology((3, 3))
        with pytest.raises(ValueError, match="entries"):
            topo.node_id((0,))

    def test_node_id_out_of_range_index_rejected(self) -> None:
        topo = TensorGridTopology((3, 3))
        with pytest.raises(ValueError, match="out of range"):
            topo.node_id((0, 3))

    def test_index_from_id_out_of_range_rejected(self) -> None:
        topo = TensorGridTopology((3, 3))
        with pytest.raises(ValueError, match="out of range"):
            topo.index_from_id(9)
        with pytest.raises(ValueError, match="out of range"):
            topo.index_from_id(-1)

    def test_neighbors_of_invalid_node_id_rejected(self) -> None:
        topo = TensorGridTopology((3, 3))
        with pytest.raises(ValueError, match="out of range"):
            topo.neighbors(100)


class TestGraphTopologyProtocol:
    def test_tensor_grid_topology_satisfies_protocol(self) -> None:
        topo = TensorGridTopology((3, 3))
        assert isinstance(topo, GraphTopology)
