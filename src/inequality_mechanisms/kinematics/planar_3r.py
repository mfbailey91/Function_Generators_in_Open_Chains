"""Planar 3R forward kinematics for Version 3 free-space studies (Sprint V3.7).

Search identity remains in actuator space ``U``; this module maps output joint
configurations ``q`` to planar tip position and heading.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def wrap_to_pi(angle: float) -> float:
    """Wrap an angle to ``(-pi, pi]``."""
    a = float(angle)
    return float((a + np.pi) % (2.0 * np.pi) - np.pi)


def angular_distance(a: float, b: float) -> float:
    """Absolute wrapped angular distance on ``(-pi, pi]``."""
    return abs(wrap_to_pi(float(a) - float(b)))


@dataclass(frozen=True, slots=True)
class Planar3R:
    """Planar three-revolute open chain with relative joint angles.

    Forward map:

    .. math::

        x = L_1\\cos q_1 + L_2\\cos(q_1+q_2) + L_3\\cos(q_1+q_2+q_3)

        y = L_1\\sin q_1 + L_2\\sin(q_1+q_2) + L_3\\sin(q_1+q_2+q_3)

        \\phi = q_1 + q_2 + q_3
    """

    L1: float = 1.0
    L2: float = 1.0
    L3: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (("L1", self.L1), ("L2", self.L2), ("L3", self.L3)):
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive, got {value}")

    def forward(self, q: ArrayLike) -> NDArray[np.float64]:
        """Return tip position ``(x, y)``."""
        q1, q2, q3 = _as_q3(q)
        th1 = q1
        th2 = q1 + q2
        th3 = q1 + q2 + q3
        x = self.L1 * np.cos(th1) + self.L2 * np.cos(th2) + self.L3 * np.cos(th3)
        y = self.L1 * np.sin(th1) + self.L2 * np.sin(th2) + self.L3 * np.sin(th3)
        return np.asarray([x, y], dtype=np.float64)

    def heading(self, q: ArrayLike) -> float:
        """Return planar tip heading ``phi = q1+q2+q3`` wrapped to ``(-pi, pi]``."""
        q1, q2, q3 = _as_q3(q)
        return wrap_to_pi(q1 + q2 + q3)

    def forward_pose(
        self, q: ArrayLike
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return ``(position, orientation)`` with orientation shape ``(1,)``."""
        tip = self.forward(q)
        phi = self.heading(q)
        return tip, np.asarray([phi], dtype=np.float64)

    def jacobian(self, q: ArrayLike) -> NDArray[np.float64]:
        """Analytic tip Jacobian ``dx/dq``, shape ``(2, 3)``."""
        q1, q2, q3 = _as_q3(q)
        th1 = q1
        th2 = q1 + q2
        th3 = q1 + q2 + q3
        s1, c1 = np.sin(th1), np.cos(th1)
        s2, c2 = np.sin(th2), np.cos(th2)
        s3, c3 = np.sin(th3), np.cos(th3)
        return np.asarray(
            [
                [
                    -self.L1 * s1 - self.L2 * s2 - self.L3 * s3,
                    -self.L2 * s2 - self.L3 * s3,
                    -self.L3 * s3,
                ],
                [
                    self.L1 * c1 + self.L2 * c2 + self.L3 * c3,
                    self.L2 * c2 + self.L3 * c3,
                    self.L3 * c3,
                ],
            ],
            dtype=np.float64,
        )

    def inverse_pose(
        self,
        position: ArrayLike,
        phi: float,
        *,
        tolerance: float = 1e-10,
    ) -> tuple[NDArray[np.float64], ...]:
        """Return analytic IK configurations for tip ``(x,y)`` and heading ``phi``.

        Reduces to planar 2R IK on the wrist after subtracting the distal link
        along ``phi``. Solutions are ordered with positive wrist ``q2`` first.
        """
        x_arr = np.asarray(position, dtype=np.float64)
        if x_arr.shape != (2,) or not np.all(np.isfinite(x_arr)):
            raise ValueError("position must be a finite vector with shape (2,)")
        if not np.isfinite(phi):
            raise ValueError("phi must be finite")
        if not np.isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("tolerance must be finite and nonnegative")

        phi_w = wrap_to_pi(phi)
        wrist = x_arr - self.L3 * np.asarray(
            [np.cos(phi_w), np.sin(phi_w)], dtype=np.float64
        )
        wx, wy = float(wrist[0]), float(wrist[1])
        r2 = wx * wx + wy * wy
        cos_q2 = (r2 - self.L1**2 - self.L2**2) / (2.0 * self.L1 * self.L2)
        if cos_q2 < -1.0 - tolerance or cos_q2 > 1.0 + tolerance:
            return ()
        cos_q2 = float(np.clip(cos_q2, -1.0, 1.0))
        q2_abs = float(np.arccos(cos_q2))
        q2_values = (q2_abs,) if abs(q2_abs) <= tolerance else (q2_abs, -q2_abs)
        out: list[NDArray[np.float64]] = []
        seen: set[tuple[float, float, float]] = set()
        for q2 in q2_values:
            q1 = float(
                np.arctan2(wy, wx)
                - np.arctan2(self.L2 * np.sin(q2), self.L1 + self.L2 * np.cos(q2))
            )
            q3 = wrap_to_pi(phi_w - q1 - q2)
            key = (
                round(q1, 12),
                round(q2, 12),
                round(q3, 12),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(np.asarray([q1, q2, q3], dtype=np.float64))
        return tuple(out)

    def inverse_position_at_heading(
        self,
        position: ArrayLike,
        phi: float,
        *,
        tolerance: float = 1e-10,
    ) -> tuple[NDArray[np.float64], ...]:
        """IK for a Cartesian tip with a frozen free heading ``phi``."""
        return self.inverse_pose(position, phi, tolerance=tolerance)


def planar_3r_elbow_family(q: ArrayLike, *, tolerance: float = 1e-9) -> str:
    """Label the middle-joint elbow sign for provenance."""
    q_arr = _as_q3(q)
    s = float(np.sin(q_arr[1]))
    if abs(s) <= tolerance:
        return "singular"
    return "elbow_up" if s > 0.0 else "elbow_down"


def _as_q3(q: ArrayLike) -> tuple[float, float, float]:
    arr = np.asarray(q, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"q must be 1-D, got shape {arr.shape}")
    if arr.shape[0] != 3:
        raise ValueError(f"q must have length 3, got length {arr.shape[0]}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("q must contain only finite values")
    return float(arr[0]), float(arr[1]), float(arr[2])
