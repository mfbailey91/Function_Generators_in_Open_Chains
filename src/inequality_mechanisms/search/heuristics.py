"""Heuristics for A* on mechanism graphs.

Version 1 uses Euclidean distance in the shared output chart Q (ADR-011),
which is admissible and consistent when edge costs are
``d_Q(g(u_a), g(u_b))``.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.output_space import OutputSpace

Heuristic = Callable[[int], float]


def output_euclidean_heuristic(
    mechanism: Mechanism,
    q_goal: ArrayLike,
    output_of: Callable[[int], NDArray[np.floating]],
    *,
    output_space: OutputSpace,
) -> Heuristic:
    """Build ``h(n) = d_Q(q_n, q_goal)``.

    Parameters
    ----------
    mechanism :
        Unused for evaluation but documents that ``q`` comes from ``g``.
        Kept for API symmetry with cost helpers.
    q_goal :
        Goal output configuration, shape ``(output_dim,)`` (raw or chart).
    output_of :
        Map from flat node id to cached **canonicalized** output
        configuration.
    output_space :
        Shared output configuration space (ADR-011).

    Returns
    -------
    callable
        Heuristic ``h(node_id) -> float``.
    """
    del mechanism  # documented coupling; evaluation uses cached outputs
    q_g = output_space.canonicalize(q_goal)

    def h(node_id: int) -> float:
        q = np.asarray(output_of(node_id), dtype=np.float64)
        if q.shape != q_g.shape:
            raise ValueError(
                f"output dim mismatch: node has {q.shape}, goal has {q_g.shape}"
            )
        return float(np.linalg.norm(q - q_g))

    return h


def zero_heuristic(_node_id: int) -> float:
    """Dijkstra heuristic ``h ≡ 0``."""
    return 0.0
