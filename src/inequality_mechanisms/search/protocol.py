"""Minimal graph protocol consumed by the generic search core (Sprint V2.1).

``best_first_search`` (and, through it, Dijkstra and A*) must see only node
ids, validity, adjacency, an edge cost, and a heuristic. It must not reach
through a graph into mechanism, coordinate, or grid internals. Concrete
Version 1 graphs (``ConstrainedInputGraph``) satisfy this protocol through an
adapter in ``graphs/adapters.py`` rather than by changing their public shape.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol, runtime_checkable


@runtime_checkable
class SearchGraph(Protocol):
    """Structural contract required by the generic search core.

    Implementations expose flat integer node ids in ``[0, node_count)``.
    Deliberately excluded: coordinates, mechanism state, ``q_state()`` /
    ``u_state()``, and any grid-specific indexing.
    """

    @property
    def node_count(self) -> int:
        """Total number of node ids, including any invalid ones."""
        ...

    def node_is_valid(self, node_id: int) -> bool:
        """Return whether ``node_id`` is a valid, searchable node."""
        ...

    def neighbors(self, node_id: int) -> Iterable[int]:
        """Return valid neighbor node ids of ``node_id``, in a fixed order."""
        ...


EdgeCost = Callable[[int, int], float]
"""Nonnegative edge weight ``(u_id, v_id) -> float``."""

Heuristic = Callable[[int], float]
"""Cost-to-go estimate ``h(node_id) -> float``."""

GoalTest = Callable[[int], bool]
"""Goal-set membership predicate ``goal_test(node_id) -> bool``."""
