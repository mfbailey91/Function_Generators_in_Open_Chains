"""Tests for shared output joint limits."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.spaces import OutputJointLimits


class TestOutputJointLimits:
    def test_contains_closed_box(self) -> None:
        limits = OutputJointLimits.box(lower=[0.0, -1.0], upper=[np.pi, 1.0])
        assert limits.dim == 2
        assert limits.contains([0.0, -1.0]) is True
        assert limits.contains([np.pi, 1.0]) is True
        assert limits.contains([0.5, 0.0]) is True
        assert limits.contains([-0.01, 0.0]) is False
        assert limits.contains([0.0, 1.01]) is False

    def test_rejects_non_strict_bounds(self) -> None:
        with pytest.raises(ValueError, match="strictly greater"):
            OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 0.0])

    def test_rejects_shape_mismatch(self) -> None:
        with pytest.raises(ValueError, match="same shape"):
            OutputJointLimits.box(lower=[0.0], upper=[1.0, 2.0])

    def test_rejects_non_finite(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            OutputJointLimits.box(lower=[0.0], upper=[np.inf])

    def test_contains_rejects_wrong_dim(self) -> None:
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        with pytest.raises(ValueError, match="length 2"):
            limits.contains([0.5])

    def test_round_trip_dict(self) -> None:
        limits = OutputJointLimits.box(lower=[-0.5, 0.25], upper=[1.5, 2.0])
        restored = OutputJointLimits.from_dict(limits.to_dict())
        assert restored.dim == 2
        assert restored.lower == pytest.approx(limits.lower)
        assert restored.upper == pytest.approx(limits.upper)
