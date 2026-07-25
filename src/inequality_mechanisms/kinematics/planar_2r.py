"""Planar 2R forward kinematics for Cartesian visualization.

Search identity remains in input space U; this module only maps output
joint configurations ``q`` to Cartesian poses ``x = f(q)`` for figures.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class Planar2R:
    """Equal-dimension planar two-revolute open chain.

    Parameters
    ----------
    L1, L2 :
        Link lengths (must be finite and positive). Defaults are unit
        lengths matching the Version 1 paper framing.
    """

    L1: float = 1.0
    L2: float = 1.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.L1) or self.L1 <= 0.0:
            raise ValueError(f"L1 must be finite and positive, got {self.L1}")
        if not np.isfinite(self.L2) or self.L2 <= 0.0:
            raise ValueError(f"L2 must be finite and positive, got {self.L2}")

    def forward(self, q: ArrayLike) -> NDArray[np.floating]:
        """Return end-effector position ``(x, y)`` for joint angles ``q``.

        Uses

        .. math::

            x = L_1\\cos q_1 + L_2\\cos(q_1+q_2)

            y = L_1\\sin q_1 + L_2\\sin(q_1+q_2)

        Parameters
        ----------
        q :
            Joint configuration, shape ``(2,)``.

        Returns
        -------
        ndarray
            Cartesian tip ``(x, y)``.
        """
        q_arr = _as_q2(q)
        q1, q2 = float(q_arr[0]), float(q_arr[1])
        x = self.L1 * np.cos(q1) + self.L2 * np.cos(q1 + q2)
        y = self.L1 * np.sin(q1) + self.L2 * np.sin(q1 + q2)
        return np.asarray([x, y], dtype=np.float64)

    def elbow(self, q: ArrayLike) -> NDArray[np.floating]:
        """Return the intermediate joint position ``(x, y)``."""
        q_arr = _as_q2(q)
        q1 = float(q_arr[0])
        return np.asarray(
            [self.L1 * np.cos(q1), self.L1 * np.sin(q1)],
            dtype=np.float64,
        )

    def link_polyline(self, q: ArrayLike) -> NDArray[np.floating]:
        """Return base–elbow–tip polyline, shape ``(3, 2)``."""
        tip = self.forward(q)
        mid = self.elbow(q)
        return np.asarray(
            [[0.0, 0.0], [mid[0], mid[1]], [tip[0], tip[1]]],
            dtype=np.float64,
        )

    def jacobian(self, q: ArrayLike) -> NDArray[np.floating]:
        """Analytic Jacobian ``dx/dq``, shape ``(2, 2)``."""
        q_arr = _as_q2(q)
        q1, q2 = float(q_arr[0]), float(q_arr[1])
        s1 = np.sin(q1)
        c1 = np.cos(q1)
        s12 = np.sin(q1 + q2)
        c12 = np.cos(q1 + q2)
        return np.asarray(
            [
                [-self.L1 * s1 - self.L2 * s12, -self.L2 * s12],
                [self.L1 * c1 + self.L2 * c12, self.L2 * c12],
            ],
            dtype=np.float64,
        )


def _as_q2(q: ArrayLike) -> NDArray[np.floating]:
    arr = np.asarray(q, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"q must be 1-D, got shape {arr.shape}")
    if arr.shape[0] != 2:
        raise ValueError(f"q must have length 2, got length {arr.shape[0]}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("q must contain only finite values")
    return arr
