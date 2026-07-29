"""Heuristics for A* on mechanism graphs.

Version 1 default uses Euclidean distance in the shared output chart Q
(ADR-011), which is admissible and consistent when edge costs are
``d_Q(g(u_a), g(u_b))``.

Sprint Four adds admissible heuristics for uniform hop cost and input
Euclidean cost (S4-02).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.costs import wrapped_input_displacement
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.search.protocol import Heuristic
from inequality_mechanisms.spaces.output_space import OutputSpace

__all__ = [
    "Heuristic",
    "input_euclidean_heuristic",
    "output_euclidean_heuristic",
    "uniform_step_heuristic",
    "zero_heuristic",
]


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


def _toroidal_index_distance(i: int, j: int, n: int, *, wrap: bool) -> int:
    """Shortest index distance on a line or cycle of length ``n``."""
    d = abs(int(i) - int(j))
    if wrap and n > 0:
        d = min(d, n - d)
    return int(d)


def uniform_step_heuristic(
    graph: ConstrainedInputGraph,
    goal: int,
) -> Heuristic:
    """Admissible lattice Manhattan lower bound for unit edge costs.

    Missing valid edges can only lengthen paths, so wrapped Manhattan
    distance in index space never overestimates hop count.
    """
    grid = graph.grid
    g0, g1 = grid.indices_from_id(int(goal))
    n0, n1 = grid.shape
    w0, w1 = grid.wrap

    def h(node_id: int) -> float:
        i0, i1 = grid.indices_from_id(int(node_id))
        return float(
            _toroidal_index_distance(i0, g0, n0, wrap=w0)
            + _toroidal_index_distance(i1, g1, n1, wrap=w1)
        )

    return h


def input_euclidean_heuristic(
    graph: ConstrainedInputGraph,
    goal: int,
) -> Heuristic:
    """Admissible ``h(n) = d_U(u_n, u_goal)`` for input Euclidean edge costs."""
    grid = graph.grid
    wrap = grid.wrap
    u_goal = np.asarray(
        grid.coordinates(*grid.indices_from_id(int(goal))),
        dtype=np.float64,
    )

    def h(node_id: int) -> float:
        u = np.asarray(
            grid.coordinates(*grid.indices_from_id(int(node_id))),
            dtype=np.float64,
        )
        return wrapped_input_displacement(u, u_goal, wrap=wrap)

    return h
