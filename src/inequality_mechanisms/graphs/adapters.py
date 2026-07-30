"""Adapters exposing Version 1 graphs through the generic search protocol.

Sprint V2.1 keeps ``ConstrainedInputGraph``'s existing two-index API
(``node_is_valid(i0, i1)``, ``neighbors(i0, i1)``) unchanged and adds this
thin wrapper so search code can depend on the minimal
``search.protocol.SearchGraph`` contract instead of reaching into
``ConstrainedInputGraph`` or ``PeriodicGrid2D`` directly.

The adapter's neighbor translation is written against the same informal
two-index duck type documented on ``MonotonicOutputGraph`` (``.grid``,
``.neighbors(i0, i1)``, ``.node_is_valid_id``) rather than against
``ConstrainedInputGraph.neighbors_by_id`` specifically. Version 1 search
entry points (``dijkstra``, ``astar``, ``reverse_dijkstra``) are called with
either graph type today, and both must keep working through this adapter.
"""

from __future__ import annotations

from typing import Protocol

from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph


class _TwoIndexGraph(Protocol):
    """Informal Version 1 duck type shared by graph-like search inputs.

    ``ConstrainedInputGraph`` and ``MonotonicOutputGraph`` both satisfy this
    shape; the adapter accepts either without importing the latter (which
    would introduce an unwanted dependency direction).
    """

    @property
    def grid(self) -> PeriodicGrid2D: ...

    def node_is_valid_id(self, node_id: int) -> bool: ...

    def neighbors(self, i0: int, i1: int) -> list[tuple[int, int]]: ...


class ConstrainedInputSearchAdapter:
    """Expose a Version 1 two-index graph through the ``SearchGraph`` protocol.

    Neighbor order matches the pre-Sprint-V2.1 inline loop in
    ``search/core.py`` (``graph.neighbors(i0, i1)`` composed with
    ``PeriodicGrid2D.node_id``). Expansion order and tie-breaking are
    therefore unchanged for Version 1 callers.

    Parameters
    ----------
    graph :
        A ``ConstrainedInputGraph`` (or another object matching the same
        ``.grid`` / ``.neighbors(i0, i1)`` / ``.node_is_valid_id`` shape,
        such as ``MonotonicOutputGraph``) to adapt.
    """

    def __init__(self, graph: ConstrainedInputGraph | _TwoIndexGraph) -> None:
        self._graph = graph

    @property
    def graph(self) -> ConstrainedInputGraph | _TwoIndexGraph:
        """Underlying constrained input graph."""
        return self._graph

    @property
    def node_count(self) -> int:
        """Total number of lattice nodes, including invalid ones."""
        return self._graph.grid.node_count

    def node_is_valid(self, node_id: int) -> bool:
        """Return whether ``node_id`` is valid under graph constraints."""
        return self._graph.node_is_valid_id(node_id)

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        """Valid neighbor flat node ids of ``node_id``."""
        grid = self._graph.grid
        i0, i1 = grid.indices_from_id(node_id)
        return tuple(grid.node_id(j0, j1) for j0, j1 in self._graph.neighbors(i0, i1))
