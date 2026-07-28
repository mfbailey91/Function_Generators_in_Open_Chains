"""Search result types and instrumentation counters.

Expansion semantics are frozen in ``docs/ADR-005-search-semantics.md``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Outcome of an instrumented graph search.

    Attributes
    ----------
    found :
        Whether a finite-cost path from start to goal exists.
    path :
        Ordered flat node ids from start to goal (inclusive). Empty when
        ``found`` is ``False``.
    cost :
        Optimal path cost ``C*`` under the search edge weights. ``inf`` when
        not found.
    n_expanded :
        Nodes removed from the open set at their best-known ``g`` whose
        outgoing edges were examined. Stale heap entries are not counted.
    n_generated :
        Number of open-set pushes (including the start node).
    n_stale :
        Heap pops discarded because their ``g`` was strictly worse than the
        best-known ``g`` for that node.
    expanded_nodes :
        Flat ids expanded in order when ``record_expanded=True`` was passed
        to search; otherwise empty.
    """

    found: bool
    path: tuple[int, ...]
    cost: float
    n_expanded: int
    n_generated: int
    n_stale: int
    expanded_nodes: tuple[int, ...] = ()

    @property
    def n_path_edges(self) -> int:
        """Number of edges on the reconstructed path."""
        if not self.found or len(self.path) < 2:
            return 0
        return len(self.path) - 1
