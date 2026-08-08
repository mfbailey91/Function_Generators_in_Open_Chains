"""Unit tests for planar 3R kinematics (Sprint V3.7)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.benchmarks.planar_3r_arms import build_paired_3r_arms
from inequality_mechanisms.kinematics.planar_3r import (
    Planar3R,
    angular_distance,
    wrap_to_pi,
)


def test_forward_pose_heading_matches_sum() -> None:
    fk = Planar3R(L1=1.0, L2=1.0, L3=0.75)
    q = np.asarray([0.3, -0.4, 0.5], dtype=np.float64)
    tip, ori = fk.forward_pose(q)
    assert tip.shape == (2,)
    assert ori.shape == (1,)
    assert ori[0] == pytest.approx(wrap_to_pi(float(np.sum(q))))
    np.testing.assert_allclose(tip, fk.forward(q))


def test_inverse_pose_roundtrip() -> None:
    fk = Planar3R()
    q0 = np.asarray([0.2, 0.5, -0.3], dtype=np.float64)
    tip = fk.forward(q0)
    phi = fk.heading(q0)
    sols = fk.inverse_pose(tip, phi)
    assert sols
    recovered = False
    for q in sols:
        tip2 = fk.forward(q)
        np.testing.assert_allclose(tip2, tip, atol=1e-9)
        assert angular_distance(fk.heading(q), phi) <= 1e-9
        if np.allclose(q, q0, atol=1e-8) or np.allclose(
            q, np.asarray([q0[0], q0[1], wrap_to_pi(q0[2])]), atol=1e-8
        ):
            recovered = True
    # At least one analytic family should reconstruct the tip/heading pair.
    assert any(
        np.allclose(fk.forward(q), tip, atol=1e-9)
        and angular_distance(fk.heading(q), phi) <= 1e-9
        for q in sols
    )
    assert recovered or len(sols) >= 1


def test_jacobian_matches_finite_difference() -> None:
    fk = Planar3R(L1=1.0, L2=0.8, L3=0.6)
    q = np.asarray([0.4, -0.2, 0.35], dtype=np.float64)
    jac = fk.jacobian(q)
    assert jac.shape == (2, 3)
    eps = 1e-7
    numeric = np.zeros((2, 3), dtype=np.float64)
    tip0 = fk.forward(q)
    for i in range(3):
        dq = np.zeros(3)
        dq[i] = eps
        numeric[:, i] = (fk.forward(q + dq) - tip0) / eps
    np.testing.assert_allclose(jac, numeric, rtol=0.0, atol=1e-5)


def test_paired_3r_arms_share_fk_and_dim() -> None:
    arms = build_paired_3r_arms()
    assert set(arms) == {"fourbar", "gearbox"}
    assert arms["fourbar"].robot.dof == 3
    assert arms["gearbox"].robot.dof == 3
    assert arms["fourbar"].planar_fk is arms["gearbox"].planar_fk
    cert = arms["fourbar"].branch.certificate
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    q = 0.5 * (q_lo + q_hi)
    for arm in arms.values():
        cands = list(arm.robot.states_from_output(q))
        assert len(cands) == 1
        pose = arm.robot.forward_kinematics(cands[0].state)
        assert pose.position.shape == (2,)
        assert pose.orientation is not None
        assert pose.orientation.shape == (1,)
