"""Edge-cost functions for input-side mechanism graphs.

Version 1 primary cost is Euclidean displacement in the shared output chart
Q (ADR-011). Sprint Four also exposes uniform hop count and input-space
Euclidean costs through a configuration-driven registry (S4-01).

Graph-facing search must use
``ConstrainedInputGraph.output_displacement`` for output Euclidean costs
(IM-042).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.output_space import OutputSpace

CostTypeName = Literal["uniform", "input_euclidean", "output_euclidean"]
EdgeCost = Callable[[int, int], float]

KNOWN_COST_TYPES: frozenset[str] = frozenset(
    {"uniform", "input_euclidean", "output_euclidean"}
)


def graph_output_euclidean_cost(
    graph: ConstrainedInputGraph,
    u_a: ArrayLike,
    u_b: ArrayLike,
) -> float:
    """Return ``d_Q(g(u_a), g(u_b))`` through the graph output boundary.

    Parameters
    ----------
    graph :
        Constrained input graph owning the shared ``OutputSpace``.
    u_a, u_b :
        Endpoint input configurations, shape ``(input_dim,)``.

    Returns
    -------
    float
        Nonnegative Euclidean output displacement after canonicalization.
    """
    return graph.output_displacement(u_a, u_b)


def output_euclidean_cost(
    mechanism: Mechanism,
    u_a: ArrayLike,
    u_b: ArrayLike,
    *,
    output_space: OutputSpace,
) -> float:
    """Graph-free ``d_Q(g(u_a), g(u_b))`` for tests without a graph.

    Prefer :func:`graph_output_euclidean_cost` or
    ``ConstrainedInputGraph.output_displacement`` whenever a
    ``ConstrainedInputGraph`` exists (IM-042 / IM-043).

    Parameters
    ----------
    mechanism :
        Mechanism providing the forward map ``g``.
    u_a, u_b :
        Endpoint input configurations, shape ``(input_dim,)``.
    output_space :
        Shared output configuration space (ADR-011).

    Returns
    -------
    float
        Nonnegative Euclidean output displacement after canonicalization.

    Raises
    ------
    ValueError
        If either endpoint fails assembly or has invalid shape.
    """
    # Graph-free helper (IM-043): labeled raw access; no graph instance.
    q_a = mechanism.input_to_output(u_a)
    q_b = mechanism.input_to_output(u_b)
    return output_space.distance(q_a, q_b)


def uniform_edge_cost(_u: int, _v: int) -> float:
    """Unit edge weight ``c(a, b) = 1`` (hop count)."""
    return 1.0


def wrapped_input_displacement(
    u_a: ArrayLike,
    u_b: ArrayLike,
    *,
    wrap: tuple[bool, ...] | list[bool],
) -> float:
    """Return Euclidean displacement in ``U`` with optional axis wrapping.

    Periodic axes use the short arc on ``[-pi, pi]`` after identifying the
    axis with period ``2 pi`` (Version 1 actuator angles).

    Parameters
    ----------
    u_a, u_b :
        Input configurations, shape ``(input_dim,)``.
    wrap :
        Per-axis wrap flags (typically ``graph.grid.wrap``).

    Returns
    -------
    float
        Nonnegative Euclidean displacement in input coordinates.
    """
    ua = np.asarray(u_a, dtype=np.float64).reshape(-1)
    ub = np.asarray(u_b, dtype=np.float64).reshape(-1)
    if ua.shape != ub.shape:
        raise ValueError(f"u shape mismatch: {ua.shape} vs {ub.shape}")
    if len(wrap) != ua.size:
        raise ValueError(f"wrap length {len(wrap)} != input dim {ua.size}")
    delta = ub - ua
    for i, do_wrap in enumerate(wrap):
        if do_wrap:
            delta[i] = (delta[i] + np.pi) % (2.0 * np.pi) - np.pi
    return float(np.linalg.norm(delta))


def input_euclidean_cost(graph: ConstrainedInputGraph) -> EdgeCost:
    """Build lattice edge cost from short input displacement ``d_U``.

    Parameters
    ----------
    graph :
        Constrained input lattice whose ``grid.wrap`` flags control
        periodic axes.

    Returns
    -------
    callable
        ``(u_id, v_id) -> float`` edge cost.
    """
    grid = graph.grid
    wrap = grid.wrap

    def cost(u_id: int, v_id: int) -> float:
        ua = np.asarray(
            grid.coordinates(*grid.indices_from_id(u_id)),
            dtype=np.float64,
        )
        ub = np.asarray(
            grid.coordinates(*grid.indices_from_id(v_id)),
            dtype=np.float64,
        )
        return wrapped_input_displacement(ua, ub, wrap=wrap)

    return cost


def output_euclidean_edge_cost(graph: ConstrainedInputGraph) -> EdgeCost:
    """Build Version 1 output Euclidean edge cost on a constrained graph."""

    def cost(u_id: int, v_id: int) -> float:
        ua = graph.grid.coordinates(*graph.grid.indices_from_id(u_id))
        ub = graph.grid.coordinates(*graph.grid.indices_from_id(v_id))
        return graph.output_displacement(ua, ub)

    return cost


def build_edge_cost(graph: ConstrainedInputGraph, cost_type: str) -> EdgeCost:
    """Resolve a named edge cost on a fixed physical graph (S4-01).

    Parameters
    ----------
    graph :
        Shared constrained input graph for the ablation.
    cost_type :
        One of ``uniform``, ``input_euclidean``, ``output_euclidean``.

    Returns
    -------
    callable
        Edge weight ``(u_id, v_id) -> float``.

    Raises
    ------
    ValueError
        If ``cost_type`` is unknown.
    """
    name = str(cost_type)
    if name not in KNOWN_COST_TYPES:
        known = ", ".join(sorted(KNOWN_COST_TYPES))
        raise ValueError(f"unknown cost type {name!r}; expected one of: {known}")
    if name == "uniform":
        return uniform_edge_cost
    if name == "input_euclidean":
        return input_euclidean_cost(graph)
    return output_euclidean_edge_cost(graph)


def node_coordinates(graph: ConstrainedInputGraph, node_id: int) -> NDArray[np.floating]:
    """Return input coordinates for a flat node id."""
    i0, i1 = graph.grid.indices_from_id(int(node_id))
    return np.asarray(graph.grid.coordinates(i0, i1), dtype=np.float64)
