"""V4-001 transmission Jacobian on OperatingBranchRobotModel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters.operating_branch_robot import (
    OperatingBranchRobotModel,
)
from inequality_mechanisms.core.input_domain import InputDomain
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate
from inequality_mechanisms.mechanisms import (
    fixed_ratio_gearbox_branch,
    unit_gearbox_branch,
)
from inequality_mechanisms.transmission_geometry.protocols import (
    KinematicTransmissionRobotModel,
)


class _V3RobotStub:
    """RobotModel-shaped object without ``jacobian_u_to_q``."""

    @property
    def dof(self) -> int:
        return 2

    @property
    def input_domain(self) -> InputDomain:
        return InputDomain(
            lower=np.array([-1.0, -1.0]),
            upper=np.array([1.0, 1.0]),
            periodic=(False, False),
        )

    def state_from_input(
        self,
        u: Any,
        assembly_state: Mapping[str, Any] | None = None,
    ) -> PhysicalState:
        u_arr = np.asarray(u, dtype=np.float64)
        return PhysicalState(u=u_arr, q=u_arr)

    def states_from_output(self, q: Any) -> Sequence[StateCandidate]:
        return ()

    def validate_state(self, state: PhysicalState, tolerance: float) -> bool:
        return True

    def forward_kinematics(self, state: PhysicalState) -> Pose:
        return Pose(position=np.asarray(state.q, dtype=np.float64))

    def jacobian_q_to_x(self, state: PhysicalState) -> np.ndarray:
        return np.eye(2, dtype=np.float64)

    def state_within_limits(self, state: PhysicalState) -> bool:
        return True


def _identity_robot() -> OperatingBranchRobotModel:
    branch = unit_gearbox_branch(
        2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )
    return OperatingBranchRobotModel(branch=branch)


def _ratio_robot() -> OperatingBranchRobotModel:
    branch = fixed_ratio_gearbox_branch(
        [2.0, -0.5],
        input_lower=[-1.0, -1.0],
        input_upper=[1.0, 1.0],
    )
    return OperatingBranchRobotModel(branch=branch)


def test_operating_branch_robot_satisfies_v4_protocol() -> None:
    robot = _identity_robot()
    assert isinstance(robot, RobotModel)
    assert isinstance(robot, KinematicTransmissionRobotModel)
    stub = _V3RobotStub()
    assert isinstance(stub, RobotModel)
    assert not isinstance(stub, KinematicTransmissionRobotModel)


def test_identity_gearbox_jacobian_is_identity() -> None:
    robot = _identity_robot()
    state = robot.state_from_input([0.2, -0.3])
    j_g = robot.jacobian_u_to_q(state)
    assert j_g.shape == (2, 2)
    assert j_g.dtype == np.float64
    np.testing.assert_allclose(j_g, np.eye(2))
    j_g[0, 0] = 99.0
    np.testing.assert_allclose(robot.jacobian_u_to_q(state), np.eye(2))


def test_fixed_ratio_gearbox_jacobian_is_diagonal() -> None:
    robot = _ratio_robot()
    state = robot.state_from_input([0.4, -0.2])
    j_g = robot.jacobian_u_to_q(state)
    np.testing.assert_allclose(j_g, np.diag([2.0, -0.5]))
    assert j_g.dtype == np.float64


def test_fourbar_jacobian_matches_branch() -> None:
    branch = fourbar_2d_branch()
    robot = OperatingBranchRobotModel(branch=branch)
    mid = 0.5 * (
        np.asarray(branch.certificate.input_lower, dtype=np.float64)
        + np.asarray(branch.certificate.input_upper, dtype=np.float64)
    )
    state = robot.state_from_input(mid)
    j_g = robot.jacobian_u_to_q(state)
    expected = np.asarray(branch.jacobian(state.u), dtype=np.float64)
    np.testing.assert_allclose(j_g, expected)
    assert j_g.shape == (robot.dof, branch.mechanism.input_dim)
    assert j_g.dtype == np.float64


def test_inconsistent_state_is_rejected() -> None:
    robot = _identity_robot()
    state = PhysicalState(u=np.array([0.2, 0.3]), q=np.array([0.2, 0.9]))
    with pytest.raises(ValueError, match="inconsistent"):
        robot.jacobian_u_to_q(state)


def test_out_of_branch_state_is_rejected() -> None:
    robot = _identity_robot()
    state = PhysicalState(u=np.array([2.0, 0.0]), q=np.array([2.0, 0.0]))
    with pytest.raises(ValueError, match="outside the certified"):
        robot.jacobian_u_to_q(state)


def test_wrong_state_dimension_is_rejected() -> None:
    robot = _identity_robot()
    bad_u = PhysicalState(u=np.array([0.1, 0.2, 0.3]), q=np.array([0.1, 0.2]))
    with pytest.raises(ValueError, match="u shape"):
        robot.jacobian_u_to_q(bad_u)
    bad_q = PhysicalState(u=np.array([0.1, 0.2]), q=np.array([0.1]))
    with pytest.raises(ValueError, match="q shape"):
        robot.jacobian_u_to_q(bad_q)
