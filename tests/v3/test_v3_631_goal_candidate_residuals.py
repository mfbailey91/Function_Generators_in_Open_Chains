"""V3-631: goal-candidate provenance and typed residual report."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    FrozenCartesianDiskGoalGenerator,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    CartesianDiskGoal,
    CartesianDiskGoalGenerator,
    ConstraintSet,
    FreeSpaceScene,
    GoalResidual,
    GoalResidualReport,
    GoalSamplingRequest,
    InputLinearMotion,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
    StateCandidate,
    build_goal_residual_report,
    planning_result_from_dict,
    planning_result_to_dict,
)
from inequality_mechanisms.core.results import PlanningResult, ResultProvenance, Trajectory
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.planners import (
    InputLinearDirectPlanner,
    PRMPlanner,
    RRTConnectPlanner,
)
from inequality_mechanisms.planners.sampling_space import (
    match_selected_candidate,
    select_goal_candidates,
    select_goal_states,
)


def _disk_problem(
    *,
    tip_offset: tuple[float, float] = (0.25, 0.0),
    radius: float = 0.08,
) -> tuple[Any, PlanningProblem, CartesianDiskGoalGenerator]:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    start = robot.state_from_input(u_lo + 0.25 * (u_hi - u_lo))
    tip = np.asarray(robot.forward_kinematics(start).position, dtype=np.float64)
    center = tip + np.asarray(tip_offset, dtype=np.float64)
    # Keep the goal inside the reachable annulus when possible.
    reach = float(np.linalg.norm(center))
    if reach > 1.85:
        center = tip - np.asarray(tip_offset, dtype=np.float64)
    goal = CartesianDiskGoal(center=center, radius=radius, robot=robot)
    assert not goal.satisfied(start)
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=16),
        objective=ActuatorTravelObjective(),
    )
    generator = CartesianDiskGoalGenerator(planar_fk=fk)
    return robot, problem, generator


def test_select_goal_candidates_preserves_provenance() -> None:
    _robot, problem, generator = _disk_problem()
    cands = select_goal_candidates(
        problem,
        goal_generator=generator,
        max_candidates=8,
    )
    assert cands
    for cand in cands:
        assert "candidate_generator_id" in cand.provenance
        assert cand.provenance["candidate_generator_id"] == "cartesian_disk_center_ik"
        assert cand.provenance["goal_sample_id"] == "disk_center"
        assert cand.provenance["goal_sample_index"] == 0
        assert cand.provenance["goal_sample_point"] == pytest.approx(
            problem.goal.center.tolist()
        )
        assert "ik_family" in cand.provenance
    states = select_goal_states(
        problem,
        goal_generator=generator,
        max_candidates=8,
    )
    assert len(states) == len(cands)
    assert all(np.allclose(s.u, c.state.u) for s, c in zip(states, cands))


def test_direct_retains_selected_candidate_provenance() -> None:
    _robot, problem, generator = _disk_problem()
    result = InputLinearDirectPlanner(
        goal_generator=generator, max_candidates=8
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.selected_goal_state is not None
    assert result.selected_goal_candidate is not None
    assert result.selected_goal_candidate.provenance["goal_sample_id"] == "disk_center"
    assert result.selected_goal_candidate.provenance["candidate_generator_id"] == (
        "cartesian_disk_center_ik"
    )
    assert result.goal_residuals is not None
    assert result.goal_residuals.physical is not None
    assert result.final_goal_residual is result.goal_residuals.physical
    assert result.goal_residuals.attachment is None
    assert result.goal_residuals.representation is not None


def test_frozen_generator_provenance_and_direct() -> None:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    start = robot.state_from_input(u_lo + 0.3 * (u_hi - u_lo))
    tip = np.asarray(robot.forward_kinematics(start).position, dtype=np.float64)
    center = tip + np.array([0.22, 0.0])
    if float(np.linalg.norm(center)) > 1.85:
        center = tip - np.array([0.22, 0.0])
    goal = CartesianDiskGoal(center=center, radius=0.08, robot=robot)
    assert not goal.satisfied(start)
    points = (
        center.copy(),
        center + np.array([0.04, 0.0]),
        center + np.array([-0.04, 0.0]),
    )
    ids = ("center", "boundary_0deg", "boundary_180deg")
    generator = FrozenCartesianDiskGoalGenerator(
        planar_fk=fk,
        goal_points=points,
        goal_point_ids=ids,
    )
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=16),
        objective=ActuatorTravelObjective(),
    )
    cands = select_goal_candidates(
        problem, goal_generator=generator, max_candidates=16
    )
    assert cands
    assert all(
        c.provenance.get("candidate_generator_id") == "frozen_cartesian_disk_points_v1"
        for c in cands
    )
    assert any(c.provenance.get("goal_sample_id") == "center" for c in cands)
    result = InputLinearDirectPlanner(
        goal_generator=generator, max_candidates=16
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.selected_goal_candidate is not None
    assert "goal_sample_id" in result.selected_goal_candidate.provenance


def test_prm_and_rrt_match_selected_candidate() -> None:
    _robot, problem, generator = _disk_problem(tip_offset=(0.2, 0.0), radius=0.08)
    prm = PRMPlanner(
        seed=7,
        n_samples=48,
        k_neighbors=8,
        max_edge_u=1.25,
        max_goal_candidates=8,
        goal_generator=generator,
    ).solve(problem)
    assert prm.status is PlanningStatus.SUCCESS
    assert prm.selected_goal_candidate is not None
    assert np.allclose(
        prm.selected_goal_candidate.state.u, prm.selected_goal_state.u  # type: ignore[union-attr]
    )

    rrt = RRTConnectPlanner(
        seed=7,
        max_iterations=400,
        step_u=0.3,
        goal_bias=0.15,
        max_goal_candidates=8,
        goal_generator=generator,
    ).solve(problem)
    assert rrt.status is PlanningStatus.SUCCESS
    # First-root only (V3-633 deferred): provenance is for that root.
    assert rrt.selected_goal_candidate is not None
    assert rrt.selected_goal_candidate.provenance["goal_sample_id"] == "disk_center"


def test_physical_vs_margin_vs_attachment() -> None:
    robot, problem, generator = _disk_problem()
    cands = list(
        generator.generate(
            robot, problem.goal, GoalSamplingRequest(max_candidates=4)
        )
    )
    assert cands
    selected = cands[0].state
    report = build_goal_residual_report(
        problem.goal,
        selected,
        candidate=cands[0],
        attachment_residual=1.25e-3,
    )
    assert report.physical is not None
    assert report.goal_margin == pytest.approx(
        float(report.physical.extras["signed_disk_residual"])
    )
    assert report.attachment == pytest.approx(1.25e-3)
    assert report.representation is not None
    # Attachment must not replace physical.
    assert report.physical.primary != pytest.approx(1.25e-3)


def test_shared_builder_same_state_same_physical() -> None:
    _robot, problem, generator = _disk_problem()
    cands = select_goal_candidates(
        problem, goal_generator=generator, max_candidates=4
    )
    selected = cands[0].state
    a = build_goal_residual_report(problem.goal, selected, candidate=cands[0])
    b = build_goal_residual_report(problem.goal, selected, candidate=None)
    assert a.physical is not None and b.physical is not None
    assert a.physical.primary == pytest.approx(b.physical.primary)
    assert a.representation is not None
    assert b.representation is None


def test_serialize_round_trip_structured_residuals() -> None:
    state = PhysicalState(u=np.array([0.1, 0.2]), q=np.array([0.3, 0.4]))
    residual = GoalResidual(
        primary=0.05,
        components=np.array([0.03, 0.04]),
        extras={"signed_disk_residual": -0.1, "cartesian_distance": 0.05},
    )
    report = GoalResidualReport(
        physical=residual,
        goal_margin=-0.1,
        representation=1e-9,
        attachment=2e-6,
    )
    candidate = StateCandidate(
        state=state,
        residual=1e-9,
        provenance={
            "goal_sample_id": "center",
            "candidate_generator_id": "frozen_cartesian_disk_points_v1",
            "goal_sample_point": [1.0, 0.0],
        },
    )
    result = PlanningResult(
        status=PlanningStatus.SUCCESS,
        trajectory=Trajectory(states=(state,)),
        selected_goal_state=state,
        selected_goal_candidate=candidate,
        total_wall_time_s=0.01,
        objective_cost=1.0,
        path_length_u=1.0,
        path_length_q=1.0,
        path_length_x=None,
        task_class=None,
        final_goal_residual=residual,
        goal_residuals=report,
        planner_metrics={},
        provenance=ResultProvenance(architecture_version=3, planner_id="test"),
    )
    restored = planning_result_from_dict(planning_result_to_dict(result))
    assert restored.selected_goal_candidate is not None
    assert restored.selected_goal_candidate.provenance["goal_sample_id"] == "center"
    assert restored.goal_residuals is not None
    assert restored.goal_residuals.physical is not None
    assert restored.goal_residuals.physical.primary == pytest.approx(0.05)
    assert restored.goal_residuals.physical.extras["signed_disk_residual"] == pytest.approx(
        -0.1
    )
    assert restored.goal_residuals.attachment == pytest.approx(2e-6)
    assert restored.final_goal_residual is not None
    assert restored.final_goal_residual.components is not None


def test_match_selected_candidate() -> None:
    state_a = PhysicalState(u=np.array([1.0, 2.0]), q=np.array([3.0, 4.0]))
    state_b = PhysicalState(u=np.array([5.0, 6.0]), q=np.array([7.0, 8.0]))
    cands = [
        StateCandidate(state=state_a, residual=0.0, provenance={"goal_sample_id": "a"}),
        StateCandidate(state=state_b, residual=0.0, provenance={"goal_sample_id": "b"}),
    ]
    matched = match_selected_candidate(cands, state_b)
    assert matched is not None
    assert matched.provenance["goal_sample_id"] == "b"
    assert match_selected_candidate(cands, PhysicalState(u=np.zeros(2), q=np.zeros(2))) is None
