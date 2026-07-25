"""Edge-cost functions for input-side mechanism graphs.

Version 1 primary cost is Euclidean displacement in output joint space Q.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from inequality_mechanisms.mechanisms.base import Mechanism


def output_euclidean_cost(
    mechanism: Mechanism,
    u_a: ArrayLike,
    u_b: ArrayLike,
) -> float:
    """Return ``||g(u_b) - g(u_a)||_2``.

    Parameters
    ----------
    mechanism :
        Mechanism providing the forward map ``g``.
    u_a, u_b :
        Endpoint input configurations, shape ``(input_dim,)``.

    Returns
    -------
    float
        Nonnegative Euclidean output displacement.

    Raises
    ------
    ValueError
        If either endpoint fails assembly or has invalid shape.
    """
    q_a = mechanism.input_to_output(u_a)
    q_b = mechanism.input_to_output(u_b)
    return float(np.linalg.norm(q_b - q_a))
