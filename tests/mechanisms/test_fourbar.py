"""Tests for planar four-bar kinematics, branch tracking, Jacobian, and preimages."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    Mechanism,
    PlanarFourBar,
)
from inequality_mechanisms.mechanisms.fourbar import (
    freudenstein_constants,
    unwrap_follower_curve,
)

# Classic crank-rocker: shortest link is the crank; Grashof satisfied.
_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


def _central_jacobian(
    mech: Mechanism, u: np.ndarray, *, eps: float = 1e-6
) -> np.ndarray:
    """Central finite-difference approximation of ``output_jacobian``."""
    n = mech.input_dim
    m = mech.output_dim
    J = np.zeros((m, n), dtype=np.float64)
    for j in range(n):
        e = np.zeros(n, dtype=np.float64)
        e[j] = eps
        qp = mech.input_to_output(u + e)
        qm = mech.input_to_output(u - e)
        # Unwrap angular outputs for scalar/product four-bars.
        delta = qp - qm
        delta = (delta + np.pi) % (2.0 * np.pi) - np.pi
        J[:, j] = delta / (2.0 * eps)
    return J


def _wrap_pi(x: float) -> float:
    return float((x + np.pi) % (2.0 * np.pi) - np.pi)


class TestPlanarFourBarForward:
    def test_assembles_over_full_crank_cycle(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        for u in np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False):
            assert bar.valid_input([u]) is True
            q = bar.input_to_output([u])
            assert q.shape == (1,)
            assert np.isfinite(q[0])

    def test_invalid_lengths_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PlanarFourBar(a=0.0, b=1.0, c=1.0, d=1.0)
        with pytest.raises(ValueError, match="positive"):
            PlanarFourBar(a=1.0, b=-1.0, c=1.0, d=1.0)

    def test_invalid_branch_rejected(self) -> None:
        with pytest.raises(ValueError, match="branch"):
            PlanarFourBar(**_CRANK_ROCKER, branch=0)

    def test_non_assembling_geometry_reports_invalid(self) -> None:
        # Links too short to close for many crank angles.
        bar = PlanarFourBar(a=1.0, b=0.5, c=0.5, d=3.0, branch=1)
        assert bar.valid_input([0.0]) is False
        with pytest.raises(ValueError, match="assembl"):
            bar.input_to_output([0.0])

    def test_periodic_consistency(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        for u in (0.3, 1.7, 4.2):
            q0 = bar.input_to_output([u])
            q1 = bar.input_to_output([u + 2.0 * np.pi])
            q2 = bar.input_to_output([u - 2.0 * np.pi])
            assert _wrap_pi(float(q0[0] - q1[0])) == pytest.approx(0.0, abs=1e-12)
            assert _wrap_pi(float(q0[0] - q2[0])) == pytest.approx(0.0, abs=1e-12)

    def test_branches_differ_away_from_fold(self) -> None:
        open_bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        crossed = PlanarFourBar(**_CRANK_ROCKER, branch=-1)
        u = 0.8
        q_open = float(open_bar.input_to_output([u])[0])
        q_cross = float(crossed.input_to_output([u])[0])
        assert abs(_wrap_pi(q_open - q_cross)) > 0.1

    def test_wrong_shape_raises(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER)
        with pytest.raises(ValueError, match="length 1"):
            bar.input_to_output([0.0, 0.0])

    def test_serialization_round_trip(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=-1, name="fb1")
        restored = Mechanism.from_dict(bar.to_dict())
        assert isinstance(restored, PlanarFourBar)
        assert restored.branch == -1
        assert restored.lengths == pytest.approx(bar.lengths)
        u = np.array([1.1])
        assert restored.input_to_output(u) == pytest.approx(bar.input_to_output(u))


class TestBranchTracking:
    def test_unwrapped_curve_has_no_artificial_jumps(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        u = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
        q = bar.follower_curve(u, unwrap=True)
        deltas = np.diff(q)
        # Dense sampling on a crank-rocker should not jump by nearly pi.
        assert float(np.max(np.abs(deltas))) < 0.2

    def test_raw_samples_unwrap_to_continuous_curve(self) -> None:
        raw = np.array([3.0, 3.1, -3.1, -3.0])
        unwrapped = unwrap_follower_curve(raw)
        assert unwrapped[0] == pytest.approx(3.0)
        # Crossing the branch cut keeps successive steps small.
        assert float(np.max(np.abs(np.diff(unwrapped)))) < 0.5
        assert unwrapped[-1] > unwrapped[0]

    def test_both_branches_are_individually_continuous(self) -> None:
        u = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
        for branch in (1, -1):
            bar = PlanarFourBar(**_CRANK_ROCKER, branch=branch)
            q = bar.follower_curve(u, unwrap=True)
            assert float(np.max(np.abs(np.diff(q)))) < 0.25


class TestFourBarJacobian:
    def test_analytic_matches_finite_differences(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        for u0 in (0.4, 1.2, 2.5, 4.0, 5.5):
            u = np.array([u0])
            assert bar.output_jacobian(u) == pytest.approx(
                _central_jacobian(bar, u), abs=1e-6, rel=1e-4
            )

    def test_crossed_branch_jacobian_matches_fd(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=-1)
        u = np.array([0.9])
        assert bar.output_jacobian(u) == pytest.approx(
            _central_jacobian(bar, u), abs=1e-6, rel=1e-4
        )

    def test_independent_fourbars_diagonal_jacobian(self) -> None:
        mech = IndependentFourBars.from_lengths(
            [
                (1.0, 2.5, 2.0, 2.0),
                (1.2, 2.8, 2.2, 2.1),
            ],
            branch=1,
        )
        u = np.array([0.7, 1.4])
        J = mech.output_jacobian(u)
        assert J.shape == (2, 2)
        assert J[0, 1] == pytest.approx(0.0)
        assert J[1, 0] == pytest.approx(0.0)
        assert J == pytest.approx(_central_jacobian(mech, u), abs=1e-6, rel=1e-4)

    def test_freudenstein_constants_match_formula(self) -> None:
        a, b, c, d = 1.0, 2.5, 2.0, 2.0
        k1, k2, k3 = freudenstein_constants(a, b, c, d)
        assert k1 == pytest.approx(d / a)
        assert k2 == pytest.approx(d / c)
        assert k3 == pytest.approx((a * a - b * b + c * c + d * d) / (2 * a * c))


class TestPreimageLookup:
    def test_forward_of_preimages_recovers_target(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        u_seed = 1.0
        q = bar.input_to_output([u_seed])
        preimages = bar.inverse_output(q)
        assert len(preimages) >= 1
        for u in preimages:
            q_back = bar.input_to_output(u)
            assert _wrap_pi(float(q_back[0] - q[0])) == pytest.approx(0.0, abs=1e-8)

    def test_crank_rocker_interior_has_two_preimages(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        # Sample the follower range and pick an interior value.
        u_grid = np.linspace(0.0, 2.0 * np.pi, 120, endpoint=False)
        qs = bar.follower_curve(u_grid, unwrap=False)
        q_target = float(np.median(qs))
        preimages = bar.inverse_output([q_target])
        assert len(preimages) == 2
        us = sorted(float(p[0]) for p in preimages)
        assert abs(_wrap_pi(us[0] - us[1])) > 0.2

    def test_unreachable_follower_returns_empty(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        u_grid = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
        qs = bar.follower_curve(u_grid, unwrap=False)
        q_min = float(np.min(qs))
        q_max = float(np.max(qs))
        # Far outside the rocker sweep.
        assert bar.inverse_output([q_max + 1.5]) == []
        assert bar.inverse_output([q_min - 1.5]) == []

    def test_independent_preimage_cartesian_product(self) -> None:
        mech = IndependentFourBars.from_lengths(
            [
                (1.0, 2.5, 2.0, 2.0),
                (1.0, 2.5, 2.0, 2.0),
            ],
            branch=1,
        )
        u = np.array([0.6, 1.8])
        q = mech.input_to_output(u)
        preimages = mech.inverse_output(q)
        assert len(preimages) >= 1
        for p in preimages:
            assert mech.input_to_output(p) == pytest.approx(q, abs=1e-7)

    def test_serialization_round_trip_independent(self) -> None:
        mech = IndependentFourBars.from_lengths(
            [(1.0, 2.5, 2.0, 2.0), (1.1, 2.6, 2.1, 2.0)],
            branch=(1, -1),
            name="pair",
        )
        restored = Mechanism.from_dict(mech.to_dict())
        assert isinstance(restored, IndependentFourBars)
        u = np.array([0.5, 1.0])
        assert restored.input_to_output(u) == pytest.approx(mech.input_to_output(u))
        assert restored.bars[0].branch == 1
        assert restored.bars[1].branch == -1
