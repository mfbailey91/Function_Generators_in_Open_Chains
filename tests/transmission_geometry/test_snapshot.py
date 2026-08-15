"""V4-004 geometry snapshot and provenance tests."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.adapters import (
    OperatingBranchRobotModel,
    planar_2r_operating_branch_robot,
)
from inequality_mechanisms.core.input_domain import InputDomain
from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import unit_gearbox_branch
from inequality_mechanisms.transmission_geometry.errors import DifferentialShapeError
from inequality_mechanisms.transmission_geometry.snapshot import (
    GEOMETRY_SNAPSHOT_SCHEMA_VERSION,
    METRIC_STATUS_AVAILABLE,
    METRIC_STATUS_RANK_DEFICIENT,
    KinematicGeometrySnapshot,
    geometry_snapshot,
)


def _identity_planar2r_robot() -> OperatingBranchRobotModel:
    branch = unit_gearbox_branch(
        2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )
    return planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(L1=1.0, L2=1.0))


class _SingularTransmissionRobot:
    """Protocol test double with rank-deficient ``J_g``."""

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
        return float(np.linalg.norm(state.q - state.u)) <= float(tolerance)

    def forward_kinematics(self, state: PhysicalState) -> Pose:
        return Pose(position=np.asarray(state.q, dtype=np.float64))

    def jacobian_q_to_x(self, state: PhysicalState) -> np.ndarray:
        return np.eye(2, dtype=np.float64)

    def jacobian_u_to_q(self, state: PhysicalState) -> np.ndarray:
        return np.asarray([[1.0, 0.0], [0.0, 0.0]], dtype=np.float64)

    def state_within_limits(self, state: PhysicalState) -> bool:
        return True


class _MismatchedJacobianRobot(_SingularTransmissionRobot):
    def jacobian_q_to_x(self, state: PhysicalState) -> np.ndarray:
        return np.ones((2, 3), dtype=np.float64)


class _V3RobotStub:
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


def _assert_jsonable_scalars(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_jsonable_scalars(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_jsonable_scalars(item)
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int) and not isinstance(value, bool):
        assert type(value) is int
        return
    if isinstance(value, float):
        assert type(value) is float
        return
    if isinstance(value, str):
        return
    raise AssertionError(f"non-JSON scalar {type(value)!r}: {value!r}")


def test_snapshot_serialization_is_deterministic() -> None:
    robot = _identity_planar2r_robot()
    state = robot.state_from_input([0.3, 0.7])
    snapshot = geometry_snapshot(robot, state)
    record = snapshot.to_dict()
    assert list(record.keys()) == [
        "schema_version",
        "u",
        "q",
        "x",
        "jacobians",
        "rank_reports",
        "metrics",
        "provenance",
    ]
    assert record["schema_version"] == GEOMETRY_SNAPSHOT_SCHEMA_VERSION
    assert list(record["jacobians"].keys()) == ["j_u_to_q", "j_q_to_x", "j_u_to_x"]
    assert list(record["rank_reports"].keys()) == ["u_to_q", "q_to_x", "u_to_x"]
    assert list(record["metrics"].keys()) == [
        "actuator_weight",
        "actuator_metric_on_q",
        "actuator_metric_on_q_available",
        "actuator_metric_unavailable_reason",
        "mobility_on_q",
        "mobility_on_x",
        "metric_status",
    ]
    _assert_jsonable_scalars(record)
    assert snapshot.metric_status == METRIC_STATUS_AVAILABLE
    assert record["metrics"]["actuator_metric_on_q_available"] is True
    assert record["metrics"]["actuator_metric_unavailable_reason"] is None
    provenance = record["provenance"]
    assert provenance["package"] == "inequality_mechanisms.transmission_geometry"
    assert provenance["kernel"] == "v4.0"
    assert provenance["robot_type"] == "OperatingBranchRobotModel"
    assert provenance["kinematic_model_type"] == "Planar2R"
    assert provenance["kinematic_model_params"] == {"L1": 1.0, "L2": 1.0}
    assert provenance["actuator_weight_source"] == "identity_default"
    assert "planner" not in provenance
    assert "task" not in provenance
    assert "solver" not in provenance
    assert snapshot.to_dict() == record


def test_snapshot_json_round_trip() -> None:
    robot = _identity_planar2r_robot()
    state = robot.state_from_input([0.25, -0.4])
    snapshot = geometry_snapshot(
        robot,
        state,
        actuator_weight=np.diag([2.0, 0.5]),
    )
    payload = json.dumps(snapshot.to_dict())
    restored = KinematicGeometrySnapshot.from_dict(json.loads(payload))
    assert restored.to_dict() == snapshot.to_dict()
    assert restored.provenance["actuator_weight_source"] == "caller"


def test_manipulator_singularity_keeps_inverse_metric() -> None:
    robot = _identity_planar2r_robot()
    state = robot.state_from_input([0.3, 0.0])
    snapshot = geometry_snapshot(robot, state)
    assert snapshot.rank_u_to_q.full_rank is True
    assert snapshot.rank_q_to_x.full_rank is False
    assert snapshot.rank_u_to_x.full_rank is False
    assert snapshot.metric_status == METRIC_STATUS_AVAILABLE
    assert snapshot.actuator_metric_on_q is not None
    mobility = np.asarray(snapshot.mobility_on_x, dtype=np.float64)
    evals = np.linalg.eigvalsh(mobility)
    assert float(evals[0]) == pytest.approx(0.0, abs=1e-10)


def test_transmission_singularity_omits_inverse_metric() -> None:
    robot = _SingularTransmissionRobot()
    state = robot.state_from_input([0.2, -0.1])
    snapshot = geometry_snapshot(robot, state)
    assert snapshot.rank_u_to_q.full_rank is False
    assert snapshot.rank_u_to_q.rank == 1
    assert snapshot.actuator_metric_on_q is None
    assert snapshot.metric_status == METRIC_STATUS_RANK_DEFICIENT
    record = snapshot.to_dict()
    assert record["metrics"]["actuator_metric_on_q"] is None
    assert record["metrics"]["actuator_metric_on_q_available"] is False
    assert record["metrics"]["actuator_metric_unavailable_reason"] == (
        "J_g is rank-deficient"
    )
    mobility = np.asarray(snapshot.mobility_on_q, dtype=np.float64)
    np.testing.assert_allclose(mobility, [[1.0, 0.0], [0.0, 0.0]])


def test_inconsistent_state_is_rejected() -> None:
    robot = _identity_planar2r_robot()
    state = PhysicalState(u=np.array([0.2, 0.3]), q=np.array([0.2, 0.9]))
    with pytest.raises(ValueError, match="inconsistent"):
        geometry_snapshot(robot, state)


def test_missing_fk_jacobian_fails_closed() -> None:
    branch = unit_gearbox_branch(
        2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )
    robot = OperatingBranchRobotModel(branch=branch)
    state = robot.state_from_input([0.1, 0.2])
    with pytest.raises(NotImplementedError, match="jacobian_q_to_x"):
        geometry_snapshot(robot, state)


def test_dimension_mismatch_and_non_v4_robot_fail_closed() -> None:
    with pytest.raises(TypeError, match="KinematicTransmissionRobotModel"):
        geometry_snapshot(
            _V3RobotStub(),
            PhysicalState(u=np.array([0.0, 0.0]), q=np.array([0.0, 0.0])),
        )
    robot = _MismatchedJacobianRobot()
    state = robot.state_from_input([0.1, 0.2])
    with pytest.raises(DifferentialShapeError, match="inner dimensions"):
        geometry_snapshot(robot, state)
