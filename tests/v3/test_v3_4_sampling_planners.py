"""Version 3.4 tests: PRM, RRT-Connect, seed protocol, smoke."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import OperatingBranchRobotModel
from inequality_mechanisms.benchmarks import (
    TASK_ALREADY_SATISFIED,
    TASK_DIRECT_LOCAL_FEASIBLE,
    TASK_INVALID_UNREPRESENTABLE,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    build_paired_arms,
    run_sampling_smoke_pack,
    run_smoke_task,
    smoke_task_catalog,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    ConstraintSet,
    ExactOutputGoal,
    FreeSpaceScene,
    InputLinearMotion,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
)
from inequality_mechanisms.planners import PRMPlanner, RRTConnectPlanner
from inequality_mechanisms.planners.sampling_rng import make_generator


def _exact_problem(
    *,
    start_frac: tuple[float, float] = (0.2, 0.25),
    goal_frac: tuple[float, float] = (0.65, 0.7),
) -> tuple[OperatingBranchRobotModel, PlanningProblem]:
    branch = fourbar_2d_branch()
    robot = OperatingBranchRobotModel(branch=branch)
    cert = branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    start = robot.state_from_input(u_lo + np.asarray(start_frac) * (u_hi - u_lo))
    goal_state = robot.state_from_input(u_lo + np.asarray(goal_frac) * (u_hi - u_lo))
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=ExactOutputGoal(q_goal=goal_state.q.copy()),
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=12),
        objective=ActuatorTravelObjective(),
    )
    return robot, problem


def test_seed_reproducibility_prm_and_rrtconnect() -> None:
    _, problem = _exact_problem()
    seed = 42
    prm_a = PRMPlanner(seed=seed, n_samples=48, k_neighbors=8, max_edge_u=1.0).solve(
        problem
    )
    prm_b = PRMPlanner(seed=seed, n_samples=48, k_neighbors=8, max_edge_u=1.0).solve(
        problem
    )
    assert prm_a.status is PlanningStatus.SUCCESS
    assert prm_b.status is PlanningStatus.SUCCESS
    assert prm_a.objective_cost == pytest.approx(prm_b.objective_cost)
    assert len(prm_a.trajectory.states) == len(prm_b.trajectory.states)  # type: ignore[union-attr]
    assert prm_a.planner_metrics["roadmap"]["accepted_edges"] == prm_b.planner_metrics[
        "roadmap"
    ]["accepted_edges"]

    rrt_a = RRTConnectPlanner(
        seed=seed, max_iterations=400, step_u=0.3, goal_bias=0.1
    ).solve(problem)
    rrt_b = RRTConnectPlanner(
        seed=seed, max_iterations=400, step_u=0.3, goal_bias=0.1
    ).solve(problem)
    assert rrt_a.status is PlanningStatus.SUCCESS
    assert rrt_b.status is PlanningStatus.SUCCESS
    assert rrt_a.objective_cost == pytest.approx(rrt_b.objective_cost)
    assert len(rrt_a.trajectory.states) == len(rrt_b.trajectory.states)  # type: ignore[union-attr]
    assert rrt_a.planner_metrics["tree"]["iterations"] == rrt_b.planner_metrics["tree"][
        "iterations"
    ]


def test_invalid_start_and_already_satisfied() -> None:
    robot, problem = _exact_problem()
    bad_start = PhysicalState(
        u=problem.start.u,
        q=problem.start.q + 5.0,
        assembly_state=problem.start.assembly_state,
    )
    bad = PlanningProblem(
        robot=problem.robot,
        scene=problem.scene,
        start=bad_start,
        goal=problem.goal,
        path_constraints=problem.path_constraints,
        local_motion=problem.local_motion,
        objective=problem.objective,
    )
    invalid = PRMPlanner(seed=1, n_samples=8).solve(bad)
    assert invalid.status is PlanningStatus.INVALID
    assert invalid.task_class == TASK_INVALID_UNREPRESENTABLE

    already_goal = ExactOutputGoal(q_goal=problem.start.q.copy())
    already_problem = PlanningProblem(
        robot=problem.robot,
        scene=problem.scene,
        start=problem.start,
        goal=already_goal,
        path_constraints=problem.path_constraints,
        local_motion=problem.local_motion,
        objective=problem.objective,
    )
    already = RRTConnectPlanner(seed=1, max_iterations=10).solve(already_problem)
    assert already.status is PlanningStatus.SUCCESS
    assert already.task_class == TASK_ALREADY_SATISFIED
    assert already.planner_metrics["tree"]["extensions"] == 0


def test_exact_start_preserved_and_namespaced_metrics() -> None:
    _, problem = _exact_problem()
    prm = PRMPlanner(seed=3, n_samples=64, k_neighbors=8, max_edge_u=1.2).solve(problem)
    assert prm.status is PlanningStatus.SUCCESS
    assert prm.trajectory is not None
    assert prm.trajectory.states[0].u == pytest.approx(problem.start.u)
    assert "roadmap" in prm.planner_metrics
    assert prm.preprocessing_time_s is not None
    assert prm.query_time_s is not None
    assert prm.task_class == TASK_DIRECT_LOCAL_FEASIBLE
    assert prm.planner_metrics["roadmap"]["direct_connector_available"] is True
    assert prm.provenance.architecture_version == 3
    assert prm.provenance.extras["seed"] == 3

    rrt = RRTConnectPlanner(seed=3, max_iterations=500, step_u=0.3).solve(problem)
    assert rrt.status is PlanningStatus.SUCCESS
    assert rrt.trajectory is not None
    assert rrt.trajectory.states[0].u == pytest.approx(problem.start.u)
    assert "tree" in rrt.planner_metrics
    assert rrt.planner_metrics["tree"]["rewires"] == 0
    assert rrt.task_class == TASK_DIRECT_LOCAL_FEASIBLE


def test_motion_rejection_via_tiny_max_edge() -> None:
    """With a vanishing edge budget, PRM cannot attach and stays unsolved."""
    _, problem = _exact_problem(
        start_frac=(0.15, 0.2), goal_frac=(0.85, 0.9)
    )
    result = PRMPlanner(
        seed=11, n_samples=40, k_neighbors=4, max_edge_u=1e-6
    ).solve(problem)
    assert result.status is PlanningStatus.UNSOLVED
    assert result.planner_metrics["roadmap"]["accepted_edges"] == 0
    # Task class describes the problem, not whether this nonlocal planner solved it.
    assert result.task_class == TASK_DIRECT_LOCAL_FEASIBLE
    assert result.planner_metrics["roadmap"]["direct_connector_available"] is True


def test_make_generator_mixes_repetition() -> None:
    g0 = make_generator(5, repetition_index=0)
    g1 = make_generator(5, repetition_index=1)
    assert g0.integers(0, 1_000_000) != g1.integers(0, 1_000_000)


def test_prm_build_per_task_does_not_claim_multi_query_reuse() -> None:
    planner = PRMPlanner(seed=7)
    assert planner.lifecycle.name == "BUILD_PER_TASK"
    assert planner.capabilities.multi_query is False


def test_sampling_smoke_pack() -> None:
    arms = build_paired_arms()
    tasks = {t.task_id: t for t in smoke_task_catalog(arms)}
    for mech in ("fourbar", "gearbox"):
        already = tasks[f"{mech}_already_satisfied"]
        for planner_name in ("prm", "rrt_connect"):
            result = run_smoke_task(
                arms[mech], already, planner_name=planner_name  # type: ignore[arg-type]
            )
            assert result.status is PlanningStatus.SUCCESS
            assert result.task_class == TASK_ALREADY_SATISFIED

        feasible = tasks[f"{mech}_planning_feasible"]
        for planner_name in ("prm", "rrt_connect"):
            result = run_smoke_task(
                arms[mech],
                feasible,
                planner_name=planner_name,  # type: ignore[arg-type]
                seed=SMOKE_SEED,
            )
            assert result.status is PlanningStatus.SUCCESS, (
                f"{mech} {planner_name} failed: {result.planner_metrics}"
            )
            assert result.task_class == TASK_DIRECT_LOCAL_FEASIBLE
            assert result.provenance.architecture_version == 3

    rows = run_sampling_smoke_pack()
    assert len(rows) == 8  # 4 tasks × 2 planners
    assert all(r["architecture_version"] == 3 for r in rows)
    assert all(r["task_class"] is not None for r in rows)
    assert all(r["seed"] == SMOKE_SEED for r in rows)
