"""V4-007 virtual-power and mobility-descent identities."""

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
    mobility_on_q,
    pullback_covector,
    pushforward_vector,
)

_FORCE = np.asarray([1.0, -0.5], dtype=np.float64)
_TANGENTS = (
    np.asarray([1.0, 0.0], dtype=np.float64),
    np.asarray([0.0, 1.0], dtype=np.float64),
    np.asarray([0.3, -0.7], dtype=np.float64),
)


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


def _assert_virtual_power(robot, u: np.ndarray) -> None:
    state = robot.state_from_input(u)
    j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
    j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
    j_xu = composite_jacobian(j_f, j_g)
    tau_q = pullback_covector(j_f, _FORCE)
    tau_u = pullback_covector(j_g, tau_q)
    np.testing.assert_allclose(tau_u, pullback_covector(j_xu, _FORCE))
    for du in _TANGENTS:
        dq = pushforward_vector(j_g, du)
        dx = pushforward_vector(j_f, dq)
        power_u = float(tau_u @ du)
        power_q = float(tau_q @ dq)
        power_x = float(_FORCE @ dx)
        np.testing.assert_allclose(power_u, power_q, atol=1e-12, rtol=1e-12)
        np.testing.assert_allclose(power_q, power_x, atol=1e-12, rtol=1e-12)


def test_virtual_power_identity_gearbox() -> None:
    _assert_virtual_power(_identity_robot(), np.asarray([0.3, 0.7]))


def test_virtual_power_diagonal_gearbox() -> None:
    _assert_virtual_power(_ratio_robot(), np.asarray([0.25, -0.4]))


def test_virtual_power_interior_fourbar() -> None:
    robot = _fourbar_robot()
    _assert_virtual_power(robot, _interior_u(robot))


def test_virtual_power_holds_at_manipulator_singularity() -> None:
    _assert_virtual_power(_identity_robot(), np.asarray([0.3, 0.0]))


def test_mobility_descent_identity_on_regular_gearbox() -> None:
    robot = _ratio_robot()
    state = robot.state_from_input([0.2, -0.3])
    j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
    weight = np.diag([1.5, 0.8])
    covector_q = np.asarray([0.4, -0.9], dtype=np.float64)
    tau_u = pullback_covector(j_g, covector_q)
    du = -np.linalg.solve(weight, tau_u)
    dq = pushforward_vector(j_g, du)
    mobility = mobility_on_q(j_g, weight)
    np.testing.assert_allclose(dq, -mobility @ covector_q, atol=1e-12, rtol=1e-12)
