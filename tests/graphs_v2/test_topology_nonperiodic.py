"""No-periodic-neighbors invariants for Version 2 graphs (Sprint V2.3, V2-305)."""

from __future__ import annotations

from tests.graphs_v2._fixtures import (
    affine_1d_branch,
    fourbar_2d_branch,
    gearbox_2d_branch,
)

from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)


def _assert_no_wrap_neighbors(graph: EmbeddedPlanningGraph) -> None:
    assert all(w is False for w in graph.topology.wrap)
    shape = graph.topology.shape
    # Corner/edge nodes must have fewer neighbors than a fully interior node
    # would on a wrapped torus of the same shape (2 * ndim everywhere).
    ndim = len(shape)
    first_node = graph.topology.node_id(tuple(0 for _ in shape))
    last_node = graph.topology.node_id(tuple(n - 1 for n in shape))
    assert len(graph.topology.neighbors(first_node)) == ndim
    assert len(graph.topology.neighbors(last_node)) == ndim
    for node_id in (first_node, last_node):
        neighbors = set(graph.topology.neighbors(node_id))
        own_index = graph.topology.index_from_id(node_id)
        for nb in neighbors:
            nb_index = graph.topology.index_from_id(nb)
            diffs = [abs(a - b) for a, b in zip(own_index, nb_index)]
            assert sum(diffs) == 1
            assert max(diffs) == 1


class TestNoPeriodicNeighbors:
    def test_uniform_input_1d(self) -> None:
        graph = EmbeddedPlanningGraph.from_uniform_input(affine_1d_branch(), shape=(6,))
        _assert_no_wrap_neighbors(graph)

    def test_uniform_output_1d(self) -> None:
        graph = EmbeddedPlanningGraph.from_uniform_output(
            affine_1d_branch(), shape=(6,)
        )
        _assert_no_wrap_neighbors(graph)

    def test_uniform_input_2d_gearbox(self) -> None:
        graph = EmbeddedPlanningGraph.from_uniform_input(
            gearbox_2d_branch(), shape=(5, 5)
        )
        _assert_no_wrap_neighbors(graph)

    def test_uniform_output_2d_fourbar(self) -> None:
        graph = EmbeddedPlanningGraph.from_uniform_output(
            fourbar_2d_branch(), shape=(6, 6)
        )
        _assert_no_wrap_neighbors(graph)

    def test_shared_output_lattice(self) -> None:
        branch = gearbox_2d_branch()
        shared = UniformOutputLattice.from_output_space(
            branch.output_space, shape=(5, 5)
        )
        graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
        _assert_no_wrap_neighbors(graph)
