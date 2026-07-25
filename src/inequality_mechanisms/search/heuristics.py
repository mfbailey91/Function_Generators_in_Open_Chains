"""Heuristics for A* on mechanism graphs.

Version 1 uses the Euclidean distance in output joint space Q, which is
admissible and consistent when edge costs are ``||g(u_b) - g(u_a)||_2``.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism

Heuristic = Callable[[int], float]


def output_euclidean_heuristic(
    mechanism: Mechanism,
    q_goal: ArrayLike,
    output_of: Callable[[int], NDArray[np.floating]],
) -> Heuristic:
    """Build ``h(n) = ||q_n - q_goal||_2``.

    Parameters
    ----------
    mechanism :
        Unused for evaluation but documents that ``q`` comes from ``g``.
        Kept for API symmetry with cost helpers.
    q_goal :
        Goal output configuration, shape ``(output_dim,)``.
    output_of :
        Map from flat node id to cached output configuration.

    Returns
    -------
    callable
        Heuristic ``h(node_id) -> float``.
    """
    del mechanism  # documented coupling; evaluation uses cached outputs
    q_g = np.asarray(q_goal, dtype=np.float64)
    if q_g.ndim != 1:
        raise ValueError(f"q_goal must be 1-D, got shape {q_g.shape}")
    if not np.all(np.isfinite(q_g)):
        raise ValueError("q_goal must contain only finite values")

    def h(node_id: int) -> float:
        q = output_of(node_id)
        if q.shape != q_g.shape:
            raise ValueError(
                f"output dim mismatch: node has {q.shape}, goal has {q_g.shape}"
            )
        return float(np.linalg.norm(q - q_g))

    return h


def zero_heuristic(_node_id: int) -> float:
    """Dijkstra heuristic ``h ≡ 0``."""
    return 0.0
