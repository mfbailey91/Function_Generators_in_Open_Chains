"""Corrective Sprint V3.6 evidence-contract tests."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    build_problem_v2,
    goal_generator_v2,
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
    state_from_shared_q,
)
from inequality_mechanisms.benchmarks.run_free_space_evidence_v2 import (
    run_free_space_evidence_v2,
)
from inequality_mechanisms.core.goals import GoalSamplingRequest


def test_v2_contract_preserves_v1_and_resolves_shared_starts() -> None:
    contract = load_free_space_bank_v2()
    assert contract.bank_id == "free_space_planar2r_v2"
    assert contract.base_bank.bank_id == "free_space_planar2r_v1"
    arms = build_bank_arms(contract.base_bank)
    tasks = resolve_free_space_tasks_v2(contract, arms=arms)
    assert len(tasks) == len(contract.base_bank.tasks)

    for task in tasks:
        tips = []
        for mech in contract.base_bank.mechanisms:
            state = state_from_shared_q(arms[mech], task.start_q)
            np.testing.assert_allclose(state.q, task.start_q, atol=1e-9)
            tips.append(
                np.asarray(
                    arms[mech].robot.forward_kinematics(state).position,
                    dtype=np.float64,
                )
            )
        np.testing.assert_allclose(tips[0], tips[1], atol=contract.start_tip_tolerance)
        np.testing.assert_allclose(tips[0], task.start_tip, atol=contract.start_tip_tolerance)


def test_frozen_disk_points_are_deterministic_and_inside_predicate() -> None:
    contract = load_free_space_bank_v2()
    arms = build_bank_arms(contract.base_bank)
    task = resolve_free_space_tasks_v2(contract, arms=arms)[3]
    assert len(task.goal_points) == 9
    for point in task.goal_points:
        assert (
            float(np.linalg.norm(point - task.goal_center))
            <= task.goal_radius + 1e-12
        )

    arm = arms["fourbar"]
    problem = build_problem_v2(arm, task)
    generator = goal_generator_v2(arm, task)
    request = GoalSamplingRequest(
        max_candidates=contract.goal_representation.max_candidates
    )
    first = list(generator.generate(arm.robot, problem.goal, request))
    second = list(generator.generate(arm.robot, problem.goal, request))
    assert [c.provenance["goal_sample_id"] for c in first] == [
        c.provenance["goal_sample_id"] for c in second
    ]
    assert all(problem.goal.satisfied(c.state) for c in first)


def test_represented_goal_q_ordering_matches_across_mechanisms() -> None:
    contract = load_free_space_bank_v2()
    arms = build_bank_arms(contract.base_bank)
    task = resolve_free_space_tasks_v2(contract, arms=arms)[3]
    sample_ids = []
    q_orders = []
    for mech in contract.base_bank.mechanisms:
        arm = arms[mech]
        problem = build_problem_v2(arm, task)
        generator = goal_generator_v2(arm, task)
        request = GoalSamplingRequest(
            max_candidates=contract.goal_representation.max_candidates
        )
        cands = list(generator.generate(arm.robot, problem.goal, request))
        sample_ids.append([str(c.provenance["goal_sample_id"]) for c in cands])
        q_orders.append([np.asarray(c.state.q, dtype=np.float64) for c in cands])
    assert sample_ids[0] == sample_ids[1]
    assert len(q_orders[0]) == len(q_orders[1])
    for q_fb, q_gb in zip(q_orders[0], q_orders[1]):
        np.testing.assert_allclose(q_fb, q_gb, rtol=0.0, atol=1e-9)


def test_input_linear_matches_represented_goal_reference_on_small_pack() -> None:
    rows, _ = run_free_space_evidence_v2(
        deterministic_planners=("input_linear",),
        stochastic_planners=(),
        task_ids=("already_0", "near_0", "far_0"),
    )
    assert rows
    for row in rows:
        if row["status"] != "success":
            continue
        assert row["direct_goal_set_reference_cost"] is not None
        assert row["suboptimality_to_direct_reference"] == pytest.approx(
            0.0, abs=1e-9
        )


def test_lattice_short_circuits_already_and_invalid_without_skip() -> None:
    rows, _ = run_free_space_evidence_v2(
        deterministic_planners=("lattice_dijkstra_eight_integrated",),
        stochastic_planners=(),
        task_ids=("already_0", "invalid_far_tip_0"),
    )
    assert len(rows) == 4
    assert all(row["skipped"] is None for row in rows)
    already = [r for r in rows if r["task_id"] == "already_0"]
    invalid = [r for r in rows if r["task_id"] == "invalid_far_tip_0"]
    assert all(r["status"] == "success" for r in already)
    assert all(r["objective_cost"] == pytest.approx(0.0) for r in already)
    assert all(r["status"] == "invalid" for r in invalid)


def test_paired_size_stratum_is_shared_after_start_correction() -> None:
    rows, _ = run_free_space_evidence_v2(
        deterministic_planners=("input_linear",),
        stochastic_planners=(),
        task_ids=("near_0", "far_0"),
    )
    by_task = {}
    for row in rows:
        by_task.setdefault(row["task_id"], []).append(row)
    for task_rows in by_task.values():
        assert len({r["size_stratum"] for r in task_rows}) == 1
        starts = [r["presearch"]["start_tip"] for r in task_rows]
        np.testing.assert_allclose(starts[0], starts[1], atol=1e-9)


@pytest.mark.ompl
def test_process_isolated_ompl_worker_path_when_available() -> None:
    from inequality_mechanisms.adapters.ompl import is_ompl_available

    if not is_ompl_available():
        pytest.skip("OMPL Python bindings unavailable")
    rows, _ = run_free_space_evidence_v2(
        deterministic_planners=(),
        stochastic_planners=("ompl_rrt_connect",),
        seeds=(7,),
        task_ids=("near_0",),
        ompl_solve_time_s=0.5,
    )
    assert len(rows) == 2
    assert all(r["process_isolated"] for r in rows)
    assert all(r["seed"] == 7 for r in rows)
    assert all(r["skipped"] is None for r in rows)
