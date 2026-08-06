"""Version 3.2 tests: Cartesian disk goals, connectors, classification, smoke."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.benchmarks import (
    ALL_TASK_CLASSES,
    TASK_ALREADY_SATISFIED,
    TASK_CERTIFIABLY_UNREACHABLE,
    TASK_DIRECT_CONNECTOR_UNAVAILABLE,
    TASK_DIRECT_LOCAL_FEASIBLE,
    TASK_INVALID_UNREPRESENTABLE,
    UnreachabilityCertificate,
    classify_direct_attempt,
)
from inequality_mechanisms.benchmarks.smoke_direct_2r import (
    build_paired_arms,
    run_smoke_pack,
    run_smoke_task,
    smoke_task_catalog,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    CartesianDiskGoal,
    CartesianDiskGoalGenerator,
    ConstraintSet,
    FreeSpaceScene,
    GoalSamplingRequest,
    InputLinearMotion,
    OutputLinearMotion,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
)
from inequality_mechanisms.core.local_motion import EndpointDeclaredMotion
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.planners import (
    InputLinearDirectPlanner,
    OutputLinearDirectPlanner,
)


def test_cartesian_disk_goal_residual_and_satisfied() -> None:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    start = robot.state_from_input(
        0.5
        * (
            np.asarray(robot.branch.certificate.input_lower)
            + np.asarray(robot.branch.certificate.input_upper)
        )
    )
    tip = np.asarray(robot.forward_kinematics(start).position)
    goal = CartesianDiskGoal(center=tip, radius=0.05, robot=robot)
    assert goal.satisfied(start)
    residual = goal.residual(start)
    assert residual.primary == pytest.approx(0.0, abs=1e-9)
    assert residual.extras["signed_disk_residual"] == pytest.approx(-0.05, abs=1e-9)

    far = CartesianDiskGoal(center=tip + np.array([1.0, 0.0]), radius=0.05, robot=robot)
    assert not far.satisfied(start)
    assert far.residual(start).primary == pytest.approx(1.0, abs=1e-6)


def test_output_vs_input_linear_actuator_cost_properties() -> None:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    start = robot.state_from_input(u_lo + 0.2 * (u_hi - u_lo))
    end = robot.state_from_input(u_lo + 0.55 * (u_hi - u_lo))
    out = OutputLinearMotion(robot=robot, n_samples=48).connect(start, end)
    inn = InputLinearMotion(robot=robot, n_samples=48).connect(start, end)
    assert out is not None and inn is not None
    endpoint = float(np.linalg.norm(end.u - start.u))
    out_cost = float(out.parameters["actuator_path_length"])
    in_cost = float(inn.parameters["actuator_path_length"])
    assert in_cost == pytest.approx(endpoint)
    assert out_cost >= endpoint - 1e-9
    obj = ActuatorTravelObjective()
    assert obj.motion_cost(out) == pytest.approx(out_cost)
    assert obj.motion_cost(inn) == pytest.approx(in_cost)


def test_classification_string_coverage() -> None:
    assert set(ALL_TASK_CLASSES) == {
        TASK_ALREADY_SATISFIED,
        TASK_DIRECT_LOCAL_FEASIBLE,
        TASK_DIRECT_CONNECTOR_UNAVAILABLE,
        TASK_INVALID_UNREPRESENTABLE,
        TASK_CERTIFIABLY_UNREACHABLE,
    }
    assert (
        classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=True,
            candidates_representable=True,
            connector_succeeded=False,
        )
        == TASK_ALREADY_SATISFIED
    )
    assert (
        classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=True,
            connector_succeeded=True,
        )
        == TASK_DIRECT_LOCAL_FEASIBLE
    )
    assert (
        classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=True,
            connector_succeeded=False,
        )
        == TASK_DIRECT_CONNECTOR_UNAVAILABLE
    )
    assert (
        classify_direct_attempt(
            start_valid=False,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=False,
            connector_succeeded=False,
        )
        == TASK_INVALID_UNREPRESENTABLE
    )
    cert = UnreachabilityCertificate(kind="test", details={})
    assert (
        classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=True,
            connector_succeeded=False,
            certificate=cert,
        )
        == TASK_CERTIFIABLY_UNREACHABLE
    )


def test_exact_start_no_start_disk() -> None:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    # Exact physical start from actuators — no start tolerance / start disk.
    start = robot.state_from_input(u_lo + 0.25 * (u_hi - u_lo))
    goal_state = robot.state_from_input(u_lo + 0.55 * (u_hi - u_lo))
    tip = np.asarray(robot.forward_kinematics(goal_state).position)
    goal = CartesianDiskGoal(center=tip, radius=0.05, robot=robot)
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )
    assert problem.start.u == pytest.approx(start.u)
    assert not hasattr(problem, "start_tolerance")
    result = OutputLinearDirectPlanner(
        goal_generator=CartesianDiskGoalGenerator(planar_fk=fk)
    ).solve(problem)
    assert result.provenance.architecture_version == 3
    assert result.task_class is not None


def test_goal_generator_filters_to_branch() -> None:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    goal = CartesianDiskGoal(
        center=np.asarray([1.8, 0.0]), radius=0.05, robot=robot
    )
    cands = CartesianDiskGoalGenerator(planar_fk=fk).generate(
        robot, goal, GoalSamplingRequest(max_candidates=8)
    )
    assert len(cands) == 0
    assert len(fk.inverse(goal.center)) == 2


def test_smoke_pack_direct_feasible_and_provenance() -> None:
    arms = build_paired_arms()
    tasks = {t.task_id: t for t in smoke_task_catalog(arms)}
    for mech in ("fourbar", "gearbox"):
        task = tasks[f"{mech}_direct_feasible"]
        for planner_name in ("output_linear", "input_linear"):
            result = run_smoke_task(
                arms[mech], task, planner_name=planner_name  # type: ignore[arg-type]
            )
            assert result.status == PlanningStatus.SUCCESS
            assert result.task_class == TASK_DIRECT_LOCAL_FEASIBLE
            assert result.provenance.architecture_version == 3
            assert result.selected_goal_state is not None
            assert result.objective_cost is not None
            assert result.path_length_u is not None

        already = tasks[f"{mech}_already_satisfied"]
        result = run_smoke_task(arms[mech], already, planner_name="output_linear")
        assert result.status == PlanningStatus.SUCCESS
        assert result.task_class == TASK_ALREADY_SATISFIED

        invalid = tasks[f"{mech}_invalid_unrepresentable"]
        result = run_smoke_task(arms[mech], invalid, planner_name="input_linear")
        assert result.status == PlanningStatus.INVALID
        assert result.task_class == TASK_INVALID_UNREPRESENTABLE

    rows = run_smoke_pack()
    assert len(rows) == 12  # 6 tasks × 2 planners
    assert all(r["architecture_version"] == 3 for r in rows)
    assert all(r["task_class"] is not None for r in rows)


def test_direct_connector_unavailable_via_rejecting_connector() -> None:
    """When candidates exist but the connector always fails, classify unavailable."""
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    start = robot.state_from_input(
        np.asarray(cert.input_lower)
        + 0.2 * (np.asarray(cert.input_upper) - np.asarray(cert.input_lower))
    )
    goal_state = robot.state_from_input(
        np.asarray(cert.input_lower)
        + 0.55 * (np.asarray(cert.input_upper) - np.asarray(cert.input_lower))
    )
    tip = np.asarray(robot.forward_kinematics(goal_state).position)
    goal = CartesianDiskGoal(center=tip, radius=0.05, robot=robot)

    class _RejectAll:
        def connect(self, start: PhysicalState, end: PhysicalState):
            return None

    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=_RejectAll(),  # type: ignore[arg-type]
        objective=ActuatorTravelObjective(),
    )
    from inequality_mechanisms.planners.direct._common import (
        solve_with_direct_connector,
    )

    result = solve_with_direct_connector(
        problem,
        connector=_RejectAll(),
        connector_policy="reject_all_v1",
        goal_generator=CartesianDiskGoalGenerator(planar_fk=fk),
        planner_id="test_reject",
    )
    assert result.status == PlanningStatus.UNSOLVED
    assert result.task_class == TASK_DIRECT_CONNECTOR_UNAVAILABLE
