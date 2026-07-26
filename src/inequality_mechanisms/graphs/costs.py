"""Edge-cost functions for input-side mechanism graphs.

Version 1 primary cost is Euclidean displacement in the shared output chart
Q (ADR-011). Graph-facing search must use
``ConstrainedInputGraph.output_displacement`` (IM-042).
"""

from __future__ import annotations

from numpy.typing import ArrayLike

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.output_space import OutputSpace


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
