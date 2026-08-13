"""V3-634: continuous trajectory evaluation (connector-reconstructed U/Q/X)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch, gearbox_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.planar2r_visual import _pack_run
from inequality_mechanisms.audits.trajectory_evaluation import (
    SCHEMA_VERSION,
    ContinuousTrajectoryEvaluation,
    evaluate_continuous_trajectory,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    CartesianDiskGoal,
    FreeSpaceScene,
    InputLinearMotion,
    OutputLinearMotion,
    PhysicalState,
    PlanningStatus,
    Trajectory,
)
from inequality_mechanisms.core.local_motion import EndpointDeclaredMotion, LocalMotion
from inequality_mechanisms.core.results import PlanningResult, ResultProvenance
from inequality_mechanisms.core.trajectory_metrics import path_metrics_from_states
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.planners.direct._common import path_lengths_from_motion


def _gearbox_robot():
    fk = Planar2R(1.0, 1.0)
    return planar_2r_operating_branch_robot(gearbox_2d_branch(), planar_fk=fk)


def _fourbar_robot():
    fk = Planar2R(1.0, 1.0)
    return planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)


def _pair_on_branch(robot, frac_a: float, frac_b: float):
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    start = robot.state_from_input(u_lo + frac_a * (u_hi - u_lo))
    end = robot.state_from_input(u_lo + frac_b * (u_hi - u_lo))
    return start, end


def test_input_linear_straight_matches_delta_u_and_objective() -> None:
    robot = _gearbox_robot()
    start, end = _pair_on_branch(robot, 0.2, 0.55)
    connector = InputLinearMotion(robot=robot, n_samples=32)
    tip = np.asarray(robot.forward_kinematics(end).position, dtype=np.float64)
    goal = CartesianDiskGoal(center=tip, radius=0.05, robot=robot)

    cte = evaluate_continuous_trajectory(
        [start, end],
        connector=connector,
        robot=robot,
        goal=goal,
        scene=FreeSpaceScene(robot=robot),
    )

    delta_u = float(np.linalg.norm(end.u - start.u))
    motion = connector.connect(start, end)
    assert motion is not None
    objective = float(ActuatorTravelObjective().motion_cost(motion))

    assert cte.schema_version == SCHEMA_VERSION
    assert cte.connector_id == "input_linear_v1"
    assert cte.sampling_policy["n_samples"] == 32
    assert cte.all_segments_valid
    assert cte.length_u == pytest.approx(delta_u, abs=1e-12)
    assert cte.length_u == pytest.approx(objective, abs=1e-12)
    assert cte.waypoint_chord_u == pytest.approx(delta_u, abs=1e-12)
    assert cte.length_u == pytest.approx(cte.waypoint_chord_u, abs=1e-12)
    assert cte.end_physical_residual == pytest.approx(0.0, abs=1e-9)
    assert cte.start_physical_residual is not None


def test_output_linear_nonlinear_exceeds_waypoint_chord() -> None:
    robot = _fourbar_robot()
    cert = robot.branch.certificate
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    # Crossed Q endpoints make the lifted U path visibly non-chordal.
    q_a = np.array(
        [
            q_lo[0] + 0.15 * (q_hi[0] - q_lo[0]),
            q_lo[1] + 0.85 * (q_hi[1] - q_lo[1]),
        ]
    )
    q_b = np.array(
        [
            q_lo[0] + 0.85 * (q_hi[0] - q_lo[0]),
            q_lo[1] + 0.15 * (q_hi[1] - q_lo[1]),
        ]
    )
    start = robot.states_from_output(q_a)[0].state
    end = robot.states_from_output(q_b)[0].state
    connector = OutputLinearMotion(robot=robot, n_samples=48)
    motion = connector.connect(start, end)
    assert motion is not None

    cte = evaluate_continuous_trajectory(
        [start, end], connector=connector, robot=robot
    )
    chords = path_metrics_from_states([start, end], robot=robot)

    assert cte.all_segments_valid
    assert cte.length_u is not None
    assert cte.length_u >= chords.length_u - 1e-9
    assert cte.length_u != pytest.approx(chords.length_u, abs=1e-4)
    assert cte.waypoint_chord_u == pytest.approx(chords.length_u, abs=1e-12)
    assert "waypoint_chord_u" in cte.to_jsonable()
    assert cte.to_jsonable()["length_u"] == pytest.approx(cte.length_u)


def test_multi_waypoint_segment_sums_and_sample_continuity() -> None:
    robot = _gearbox_robot()
    a, b = _pair_on_branch(robot, 0.15, 0.35)
    _, c = _pair_on_branch(robot, 0.35, 0.6)
    connector = InputLinearMotion(robot=robot, n_samples=16)

    cte = evaluate_continuous_trajectory(
        Trajectory(states=(a, b, c)),
        connector=connector,
        robot=robot,
    )
    assert cte.all_segments_valid
    assert len(cte.segments) == 2
    assert cte.length_u == pytest.approx(
        float(cte.segments[0].length_u) + float(cte.segments[1].length_u),
        abs=1e-12,
    )
    assert cte.length_q == pytest.approx(
        float(cte.segments[0].length_q) + float(cte.segments[1].length_q),
        abs=1e-12,
    )
    assert cte.length_x == pytest.approx(
        float(cte.segments[0].length_x) + float(cte.segments[1].length_x),
        abs=1e-12,
    )
    assert cte.n_samples_total == 32
    # Interior waypoint continuity across reconstructed segments.
    assert np.allclose(cte.segments[0].sample_u[-1], cte.segments[1].sample_u[0])
    assert np.allclose(cte.segments[0].sample_q[-1], cte.segments[1].sample_q[0])


def test_failed_connect_does_not_chord_fill_lengths() -> None:
    robot = _gearbox_robot()
    start, end = _pair_on_branch(robot, 0.2, 0.55)
    # Endpoint-declared motions have no sample arrays → fail closed.
    connector = EndpointDeclaredMotion()
    cte = evaluate_continuous_trajectory(
        [start, end], connector=connector, robot=robot
    )
    chords = path_metrics_from_states([start, end], robot=robot)

    assert not cte.all_segments_valid
    assert len(cte.segments) == 1
    assert cte.segments[0].valid is False
    assert cte.segments[0].failure_reason == "missing_connector_samples"
    assert cte.length_u is None
    assert cte.length_q is None
    assert cte.length_x is None
    assert cte.waypoint_chord_u == pytest.approx(chords.length_u, abs=1e-12)
    assert cte.waypoint_chord_q == pytest.approx(chords.length_q, abs=1e-12)


def test_failed_connect_rejected_records_reason() -> None:
    robot = _fourbar_robot()
    start, end = _pair_on_branch(robot, 0.2, 0.55)

    class _RejectConnector:
        model_id = "reject_v1"
        n_samples = 8

        def connect(self, a: PhysicalState, b: PhysicalState) -> LocalMotion | None:
            return None

    cte = evaluate_continuous_trajectory(
        [start, end], connector=_RejectConnector(), robot=robot
    )
    assert not cte.all_segments_valid
    assert cte.segments[0].failure_reason == "connect_rejected"
    assert cte.length_u is None


def test_direct_single_edge_parity_with_path_lengths_from_motion() -> None:
    robot = _fourbar_robot()
    start, end = _pair_on_branch(robot, 0.25, 0.5)
    connector = OutputLinearMotion(robot=robot, n_samples=40)
    motion = connector.connect(start, end)
    assert motion is not None
    lu, lq, lx = path_lengths_from_motion(motion, robot=robot)

    cte = evaluate_continuous_trajectory(
        [start, end], connector=connector, robot=robot
    )
    assert cte.all_segments_valid
    assert cte.length_u == pytest.approx(lu, abs=1e-12)
    assert cte.length_q == pytest.approx(lq, abs=1e-12)
    if lx is None:
        assert cte.length_x is None
    else:
        assert cte.length_x == pytest.approx(lx, abs=1e-12)


def test_schema_and_diagnostic_chord_names() -> None:
    robot = _gearbox_robot()
    start, end = _pair_on_branch(robot, 0.1, 0.4)
    cte = evaluate_continuous_trajectory(
        [start, end],
        connector=InputLinearMotion(robot=robot, n_samples=12),
        robot=robot,
    )
    payload = cte.to_jsonable()
    assert payload["schema_version"] == "v3_6c_cte_v1"
    assert payload["connector_id"]
    assert "waypoint_chord_u" in payload
    assert "waypoint_chord_q" in payload
    assert "waypoint_chord_x" in payload
    # Reporting lengths must not reuse chord field names.
    assert "chord_u" not in payload
    assert isinstance(cte, ContinuousTrajectoryEvaluation)


def test_pack_run_attaches_continuous_and_preserves_objective() -> None:
    robot = _gearbox_robot()
    start, end = _pair_on_branch(robot, 0.2, 0.5)
    connector = InputLinearMotion(robot=robot, n_samples=24)
    motion = connector.connect(start, end)
    assert motion is not None
    objective = float(ActuatorTravelObjective().motion_cost(motion))
    tip = np.asarray(robot.forward_kinematics(end).position, dtype=np.float64)
    goal = CartesianDiskGoal(center=tip, radius=0.1, robot=robot)
    scene = FreeSpaceScene(robot=robot)
    # Deliberately wrong planner path_length_* (chords) vs true objective.
    wrong_chord = float(np.linalg.norm(end.u - start.u)) * 0.5
    planning = PlanningResult(
        status=PlanningStatus.SUCCESS,
        trajectory=Trajectory(states=(start, end)),
        selected_goal_state=end,
        total_wall_time_s=0.01,
        objective_cost=objective,
        path_length_u=wrong_chord,
        path_length_q=wrong_chord,
        path_length_x=wrong_chord,
        task_class="direct_local_feasible",
        final_goal_residual=goal.residual(end),
        planner_metrics={"family": "test"},
        provenance=ResultProvenance(architecture_version=3, planner_id="test_pack"),
    )
    packed = _pack_run(
        planner="input_linear",
        mechanism="gearbox",
        result=planning,
        skipped=None,
        expanded=None,
        sink=None,
        robot=robot,
        connector=connector,
        goal=goal,
        scene=scene,
    )
    assert packed.objective_cost == pytest.approx(objective, abs=1e-12)
    assert packed.objective_cost != pytest.approx(wrong_chord, abs=1e-6)
    assert packed.path_length_u == pytest.approx(objective, abs=1e-12)
    assert packed.path_length_u != pytest.approx(wrong_chord, abs=1e-6)
    cte = packed.planner_metrics["continuous_trajectory"]
    assert cte["schema_version"] == SCHEMA_VERSION
    assert cte["all_segments_valid"] is True
    assert packed.planner_metrics["family"] == "test"


def test_exports_from_audits_package() -> None:
    from inequality_mechanisms import audits

    assert hasattr(audits, "evaluate_continuous_trajectory")
    assert hasattr(audits, "ContinuousTrajectoryEvaluation")
    assert hasattr(audits, "TrajectorySegmentEvaluation")
