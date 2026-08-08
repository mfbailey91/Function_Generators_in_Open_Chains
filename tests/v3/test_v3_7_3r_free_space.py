"""Sprint V3.7 planar 3R free-space tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from inequality_mechanisms.benchmarks.free_space_bank_3r import (
    build_bank_arms_3r,
    build_problem_3r,
    goal_generator_3r,
    load_free_space_bank_3r,
    max_candidates_3r,
    resolve_free_space_tasks_3r,
    state_from_shared_q_3r,
)
from inequality_mechanisms.benchmarks.run_free_space_evidence_3r import (
    run_free_space_evidence_3r,
)
from inequality_mechanisms.benchmarks.smoke_sampling_3r import (
    run_planar3r_planner_smoke,
)
from inequality_mechanisms.core.goals import (
    GoalSamplingRequest,
    PlanarPoseRegionGoal,
)
from inequality_mechanisms.kinematics.planar_3r import angular_distance, wrap_to_pi


def test_bank_resolves_shared_starts_and_pose() -> None:
    contract = load_free_space_bank_3r()
    assert contract.bank_id == "free_space_planar3r_v1"
    arms = build_bank_arms_3r(contract)
    tasks = resolve_free_space_tasks_3r(contract, arms=arms)
    assert len(tasks) == len(contract.tasks)
    assert {t.task_family for t in tasks} == {"position_only", "full_pose"}

    for task in tasks:
        tips = []
        phis = []
        for mech in contract.mechanisms:
            state = state_from_shared_q_3r(arms[mech], task.start_q)
            np.testing.assert_allclose(state.q, task.start_q, atol=1e-9)
            pose = arms[mech].robot.forward_kinematics(state)
            tips.append(np.asarray(pose.position, dtype=np.float64))
            assert pose.orientation is not None
            phis.append(float(pose.orientation[0]))
        np.testing.assert_allclose(
            tips[0], tips[1], atol=contract.start_tip_tolerance
        )
        np.testing.assert_allclose(
            tips[0], task.start_tip, atol=contract.start_tip_tolerance
        )
        assert angular_distance(phis[0], phis[1]) <= contract.start_heading_tolerance


def test_position_only_redundant_generator_is_deterministic() -> None:
    contract = load_free_space_bank_3r()
    arms = build_bank_arms_3r(contract)
    task = next(
        t
        for t in resolve_free_space_tasks_3r(contract, arms=arms)
        if t.task_id == "pos_near_0"
    )
    arm = arms["fourbar"]
    problem = build_problem_3r(arm, task)
    generator = goal_generator_3r(arm, task, contract)
    request = GoalSamplingRequest(max_candidates=max_candidates_3r(task, contract))
    first = list(generator.generate(arm.robot, problem.goal, request))
    second = list(generator.generate(arm.robot, problem.goal, request))
    assert first
    assert [c.provenance["goal_sample_id"] for c in first] == [
        c.provenance["goal_sample_id"] for c in second
    ]
    assert all(problem.goal.satisfied(c.state) for c in first)
    phi_ids = {c.provenance.get("goal_phi_index") for c in first}
    assert None not in phi_ids
    assert len(phi_ids) >= 1


def test_full_pose_wrapping_and_orientation_residual() -> None:
    contract = load_free_space_bank_3r()
    arms = build_bank_arms_3r(contract)
    task = next(
        t
        for t in resolve_free_space_tasks_3r(contract, arms=arms)
        if t.task_id == "pose_near_0"
    )
    arm = arms["fourbar"]
    problem = build_problem_3r(arm, task)
    assert isinstance(problem.goal, PlanarPoseRegionGoal)
    assert problem.goal.phi_goal == pytest.approx(wrap_to_pi(float(task.goal_phi)))

    generator = goal_generator_3r(arm, task, contract)
    request = GoalSamplingRequest(max_candidates=max_candidates_3r(task, contract))
    cands = list(generator.generate(arm.robot, problem.goal, request))
    assert cands
    for cand in cands:
        assert problem.goal.satisfied(cand.state)
        residual = problem.goal.residual(cand.state)
        assert residual.extras["angular_distance"] <= float(task.orientation_tol) + 1e-9

    wrapped = PlanarPoseRegionGoal(
        center=task.goal_center.copy(),
        radius=task.goal_radius,
        phi_goal=float(task.goal_phi) + 2.0 * math.pi,
        orientation_tol=float(task.orientation_tol),
        robot=arm.robot,
    )
    assert wrapped.phi_goal == pytest.approx(problem.goal.phi_goal)
    assert all(wrapped.satisfied(c.state) for c in cands)


def test_represented_goal_q_parity_across_mechanisms() -> None:
    contract = load_free_space_bank_3r()
    arms = build_bank_arms_3r(contract)
    for task_id in ("pos_near_0", "pose_near_0"):
        task = next(
            t
            for t in resolve_free_space_tasks_3r(contract, arms=arms)
            if t.task_id == task_id
        )
        q_orders = []
        sample_ids = []
        for mech in contract.mechanisms:
            arm = arms[mech]
            problem = build_problem_3r(arm, task)
            generator = goal_generator_3r(arm, task, contract)
            request = GoalSamplingRequest(
                max_candidates=max_candidates_3r(task, contract)
            )
            cands = list(generator.generate(arm.robot, problem.goal, request))
            sample_ids.append([str(c.provenance["goal_sample_id"]) for c in cands])
            q_orders.append([np.asarray(c.state.q, dtype=np.float64) for c in cands])
        assert sample_ids[0] == sample_ids[1]
        assert len(q_orders[0]) == len(q_orders[1])
        for q_fb, q_gb in zip(q_orders[0], q_orders[1]):
            np.testing.assert_allclose(q_fb, q_gb, rtol=0.0, atol=1e-9)


def test_input_linear_matches_direct_reference_lower_bound() -> None:
    rows, _ = run_free_space_evidence_3r(
        deterministic_planners=("input_linear",),
        stochastic_planners=(),
        task_ids=("pos_already_0", "pos_near_0", "pose_already_0", "pose_near_0"),
    )
    assert rows
    for row in rows:
        if row["status"] != "success":
            continue
        assert row["direct_goal_set_reference_cost"] is not None
        assert row["suboptimality_to_direct_reference"] == pytest.approx(
            0.0, abs=1e-9
        )


def test_invalid_tasks_have_no_represented_candidates() -> None:
    contract = load_free_space_bank_3r()
    arms = build_bank_arms_3r(contract)
    for task_id in ("pos_invalid_0", "pose_invalid_0"):
        task = next(
            t
            for t in resolve_free_space_tasks_3r(contract, arms=arms)
            if t.task_id == task_id
        )
        arm = arms["fourbar"]
        problem = build_problem_3r(arm, task)
        generator = goal_generator_3r(arm, task, contract)
        request = GoalSamplingRequest(max_candidates=max_candidates_3r(task, contract))
        cands = list(generator.generate(arm.robot, problem.goal, request))
        assert cands == []
        assert not problem.goal.satisfied(problem.start)


def test_planner_smoke_pack_runs() -> None:
    report = run_planar3r_planner_smoke(task_id="pos_near_0", seed=7)
    assert report["dof"] == 3
    assert report["all_attempted"] is True
    assert report["direct_status"] in {"success", "unsolved", "invalid"}
