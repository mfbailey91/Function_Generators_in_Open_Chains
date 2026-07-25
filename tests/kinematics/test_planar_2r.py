"""Tests for planar 2R forward kinematics."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.kinematics import Planar2R


def _central_jacobian(arm: Planar2R, q: np.ndarray, *, eps: float = 1e-6) -> np.ndarray:
    J = np.zeros((2, 2), dtype=np.float64)
    for j in range(2):
        e = np.zeros(2, dtype=np.float64)
        e[j] = eps
        xp = arm.forward(q + e)
        xm = arm.forward(q - e)
        J[:, j] = (xp - xm) / (2.0 * eps)
    return J


class TestPlanar2R:
    def test_stretched_pose(self) -> None:
        arm = Planar2R(L1=1.0, L2=0.5)
        tip = arm.forward([0.0, 0.0])
        assert tip == pytest.approx([1.5, 0.0])
        elbow = arm.elbow([0.0, 0.0])
        assert elbow == pytest.approx([1.0, 0.0])

    def test_right_angle_pose(self) -> None:
        arm = Planar2R(L1=1.0, L2=1.0)
        q = np.array([0.0, np.pi / 2])
        tip = arm.forward(q)
        assert tip == pytest.approx([1.0, 1.0])

    def test_link_polyline_shape(self) -> None:
        arm = Planar2R()
        poly = arm.link_polyline([0.3, -0.4])
        assert poly.shape == (3, 2)
        assert poly[0] == pytest.approx([0.0, 0.0])
        assert poly[1] == pytest.approx(arm.elbow([0.3, -0.4]))
        assert poly[2] == pytest.approx(arm.forward([0.3, -0.4]))

    def test_jacobian_matches_finite_differences(self) -> None:
        arm = Planar2R(L1=1.2, L2=0.8)
        q = np.array([0.4, -0.7])
        assert arm.jacobian(q) == pytest.approx(_central_jacobian(arm, q), abs=1e-8)

    def test_invalid_lengths_raise(self) -> None:
        with pytest.raises(ValueError, match="L1"):
            Planar2R(L1=0.0, L2=1.0)
        with pytest.raises(ValueError, match="L2"):
            Planar2R(L1=1.0, L2=-1.0)

    def test_wrong_shape_raises(self) -> None:
        arm = Planar2R()
        with pytest.raises(ValueError, match="length 2"):
            arm.forward([0.0])
        with pytest.raises(ValueError, match="1-D"):
            arm.forward([[0.0, 0.0]])
        with pytest.raises(ValueError, match="finite"):
            arm.forward([np.nan, 0.0])
