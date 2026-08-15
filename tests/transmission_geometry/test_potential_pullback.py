"""V4-007 Cartesian potential-gradient pullback identities."""

from __future__ import annotations

import numpy as np
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    fixed_ratio_gearbox_branch,
    unit_gearbox_branch,
)
from inequality_mechanisms.transmission_geometry import (
    composite_jacobian,
    pullback_covector,
)

_GOAL = np.asarray([1.2, 0.4], dtype=np.float64)
_WEIGHT_X = np.diag([2.0, 0.5])
_STEP = 1e-6


def _identity_robot():
    branch = unit_gearbox_branch(
        2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )
    return planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(L1=1.0, L2=1.0))


def _ratio_robot():
    branch = fixed_ratio_gearbox_branch(
        [2.0, 0.5],
        input_lower=[-1.0, -1.0],
        input_upper=[1.0, 1.0],
    )
    return planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(L1=1.0, L2=1.0))


def _fourbar_robot():
    return planar_2r_operating_branch_robot(
        fourbar_2d_branch(), planar_fk=Planar2R(L1=1.0, L2=1.0)
    )


def _interior_u(robot) -> np.ndarray:
    cert = robot.branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    return 0.5 * (lo + hi)


def _phi(x: np.ndarray) -> float:
    delta = x - _GOAL
    return 0.5 * float(delta @ (_WEIGHT_X @ delta))


def _tip(robot, u: np.ndarray) -> np.ndarray:
    state = robot.state_from_input(u)
    return np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)


def _assert_inside_input_box(robot, u: np.ndarray, *, h: float) -> None:
    cert = robot.branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    if np.any(u - h < lo) or np.any(u + h > hi):
        raise AssertionError(
            f"finite-difference stencil leaves the certified input box: "
            f"u={u.tolist()}, h={h}, lower={lo.tolist()}, upper={hi.tolist()}"
        )


def _assert_potential_pullback(robot, u: np.ndarray, *, h: float = _STEP) -> None:
    u = np.asarray(u, dtype=np.float64)
    _assert_inside_input_box(robot, u, h=h)
    state = robot.state_from_input(u)
    j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
    j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
    j_xu = composite_jacobian(j_f, j_g)
    x = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
    grad_x = _WEIGHT_X @ (x - _GOAL)
    analytic = pullback_covector(j_xu, grad_x)
    fd = np.empty(u.shape[0], dtype=np.float64)
    eye = np.eye(u.shape[0], dtype=np.float64)
    for i in range(u.shape[0]):
        phi_plus = _phi(_tip(robot, u + h * eye[i]))
        phi_minus = _phi(_tip(robot, u - h * eye[i]))
        fd[i] = (phi_plus - phi_minus) / (2.0 * h)
    try:
        np.testing.assert_allclose(analytic, fd, atol=1e-8, rtol=1e-6)
    except AssertionError as exc:
        raise AssertionError(
            "potential-gradient pullback mismatch: "
            f"u={u.tolist()}, h={h}, analytic={analytic.tolist()}, "
            f"finite_difference={fd.tolist()}"
        ) from exc


def test_potential_pullback_identity_gearbox() -> None:
    _assert_potential_pullback(_identity_robot(), np.asarray([0.3, 0.7]))


def test_potential_pullback_diagonal_gearbox() -> None:
    _assert_potential_pullback(_ratio_robot(), np.asarray([0.25, -0.4]))


def test_potential_pullback_interior_fourbar() -> None:
    robot = _fourbar_robot()
    _assert_potential_pullback(robot, _interior_u(robot))
