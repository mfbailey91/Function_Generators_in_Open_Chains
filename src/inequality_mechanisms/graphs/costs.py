"""Edge-cost functions for input-side mechanism graphs.

Version 1 primary cost is Euclidean displacement in the shared output chart
Q (ADR-011).
"""

from __future__ import annotations

from numpy.typing import ArrayLike

from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.output_space import OutputSpace


def output_euclidean_cost(
    mechanism: Mechanism,
    u_a: ArrayLike,
    u_b: ArrayLike,
    *,
    output_space: OutputSpace,
) -> float:
    """Return ``d_Q(g(u_a), g(u_b))`` in the shared output chart.

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
    q_a = mechanism.input_to_output(u_a)
    q_b = mechanism.input_to_output(u_b)
    return output_space.distance(q_a, q_b)
