"""Tests for output configuration space (ADR-011)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.spaces import (
    AxisTopology,
    OutputAxis,
    OutputJointLimits,
    OutputSpace,
    lift_bounded_revolute,
    wrap_to_pi,
)


class TestLiftBoundedRevolute:
    def test_identity_inside_chart(self) -> None:
        q_min, q_max = 1.0, 2.0
        assert lift_bounded_revolute(1.5, q_min, q_max) == pytest.approx(1.5)

    def test_seam_crossing_sequence(self) -> None:
        # Principal values near +pi that should lift continuously above pi.
        raw = [2.967, 3.054, 3.124, -3.107, -3.020]  # ~170..187 deg
        q_min, q_max = 2.9, 3.3
        lifted = [lift_bounded_revolute(t, q_min, q_max) for t in raw]
        for i in range(1, len(lifted)):
            assert lifted[i] > lifted[i - 1] - 1e-12
        assert lifted[-1] == pytest.approx(raw[-1] + 2.0 * np.pi, abs=1e-9)

    def test_rejects_full_rotation_span(self) -> None:
        with pytest.raises(ValueError, match="2 pi"):
            lift_bounded_revolute(0.0, 0.0, 2.0 * np.pi)


class TestOutputSpace:
    def test_canonicalize_and_distance_no_shortcut(self) -> None:
        # Window almost full circle: +170 to -170 deg is long way, not short.
        lo = np.deg2rad(-170.0)
        hi = np.deg2rad(170.0)
        space = OutputSpace.bounded_revolute_box([lo], [hi])
        qa = np.array([np.deg2rad(169.0)])
        qb = np.array([np.deg2rad(-169.0)])
        dist = space.distance(qa, qb)
        short = abs(wrap_to_pi(float(qb[0] - qa[0])))
        assert dist == pytest.approx(abs(float(space.canonicalize(qb)[0] - space.canonicalize(qa)[0])))
        assert dist > np.pi
        assert dist > short

    def test_contains_uses_lift(self) -> None:
        space = OutputSpace.bounded_revolute_box([2.9], [3.3])
        # Principal -3.0 is equivalent to ~3.28 after lift into this chart.
        assert space.contains([-3.0]) is True
        assert space.contains([0.0]) is False

    def test_from_limits_round_trip(self) -> None:
        limits = OutputJointLimits.box(lower=[-0.5, 0.1], upper=[1.0, 1.5])
        space = OutputSpace.from_limits(limits)
        assert space.dim == 2
        restored = OutputSpace.from_dict(space.to_dict())
        assert restored.axes[0].topology is AxisTopology.BOUNDED_REVOLUTE
        assert restored.lower == pytest.approx(space.lower)
        assert restored.upper == pytest.approx(space.upper)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            OutputSpace(axes=())

    def test_periodic_axis_not_implemented(self) -> None:
        axis = OutputAxis(topology=AxisTopology.PERIODIC_REVOLUTE)
        with pytest.raises(NotImplementedError):
            axis.canonicalize(0.0)

    def test_displacement_vector(self) -> None:
        space = OutputSpace.bounded_revolute_box([0.0, 0.0], [1.0, 2.0])
        d = space.displacement([0.2, 0.5], [0.7, 1.5])
        assert d == pytest.approx([0.5, 1.0])
