"""Shared output joint limits in configuration space Q.

Fair Version 1 comparisons apply the same box limits to every mechanism.
Limits live in output joint space; they are not applied inside
``Mechanism.valid_input`` (assembly domain only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _as_bound_vector(x: ArrayLike, *, name: str) -> NDArray[np.floating]:
    """Validate a 1-D finite bound vector."""
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    if arr.size < 1:
        raise ValueError(f"{name} must be non-empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr.copy()


@dataclass(frozen=True, slots=True)
class OutputJointLimits:
    """Axis-aligned box limits on output joint coordinates.

    A configuration ``q`` is admissible when

    ``lower[i] <= q[i] <= upper[i]`` for every axis ``i`` (closed box).

    Parameters
    ----------
    lower :
        Per-axis lower bounds, shape ``(n,)``.
    upper :
        Per-axis upper bounds, shape ``(n,)``. Must satisfy
        ``upper[i] > lower[i]`` for all ``i``.
    """

    lower: NDArray[np.floating]
    upper: NDArray[np.floating]

    def __post_init__(self) -> None:
        lower = _as_bound_vector(self.lower, name="lower")
        upper = _as_bound_vector(self.upper, name="upper")
        if lower.shape != upper.shape:
            raise ValueError(
                f"lower and upper must have the same shape, got "
                f"{lower.shape} and {upper.shape}"
            )
        if not np.all(upper > lower):
            raise ValueError("each upper bound must be strictly greater than lower")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    @classmethod
    def box(
        cls,
        lower: ArrayLike,
        upper: ArrayLike,
    ) -> OutputJointLimits:
        """Construct limits from array-like bounds."""
        return cls(
            lower=np.asarray(lower, dtype=np.float64),
            upper=np.asarray(upper, dtype=np.float64),
        )

    @property
    def dim(self) -> int:
        """Output dimension of the limit box."""
        return int(self.lower.shape[0])

    def contains(self, q: ArrayLike) -> bool:
        """Return whether ``q`` lies in the closed limit box.

        Parameters
        ----------
        q :
            Output configuration, shape ``(dim,)``.

        Returns
        -------
        bool
            ``True`` if every coordinate satisfies the closed bounds.

        Raises
        ------
        ValueError
            If ``q`` has the wrong shape or is non-finite.
        """
        arr = np.asarray(q, dtype=np.float64)
        if arr.ndim != 1:
            raise ValueError(f"q must be 1-D, got shape {arr.shape}")
        if arr.shape[0] != self.dim:
            raise ValueError(f"q must have length {self.dim}, got {arr.shape[0]}")
        if not np.all(np.isfinite(arr)):
            raise ValueError("q must contain only finite values")
        return bool(np.all(arr >= self.lower) and np.all(arr <= self.upper))

    def to_dict(self) -> dict[str, Any]:
        """Serialize bounds to a plain dictionary."""
        return {
            "lower": self.lower.tolist(),
            "upper": self.upper.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputJointLimits:
        """Deserialize bounds from ``to_dict`` output."""
        return cls.box(lower=data["lower"], upper=data["upper"])
