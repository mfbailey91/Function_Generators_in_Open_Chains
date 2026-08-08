"""Planner smoke pack on planar 3R PlanningProblem (Sprint V3.7 / V3-703)."""

from __future__ import annotations

from typing import Any

import numpy as np

from inequality_mechanisms.benchmarks.free_space_bank_3r import (
    build_bank_arms_3r,
    build_problem_3r,
    goal_generator_3r,
    load_free_space_bank_3r,
    max_candidates_3r,
    resolve_free_space_tasks_3r,
)
from inequality_mechanisms.core.results import PlanningStatus
from inequality_mechanisms.planners.direct.input_linear import InputLinearDirectPlanner
from inequality_mechanisms.planners.roadmap import PRMPlanner
from inequality_mechanisms.planners.tree import RRTConnectPlanner


def run_planar3r_planner_smoke(
    *,
    task_id: str = "pos_near_0",
    seed: int = 7,
) -> dict[str, Any]:
    """Run a small direct/PRM/RRTConnect smoke on one frozen 3R bank task."""
    contract = load_free_space_bank_3r()
    arms = build_bank_arms_3r(contract)
    tasks = {
        t.task_id: t for t in resolve_free_space_tasks_3r(contract, arms=arms)
    }
    if task_id not in tasks:
        raise KeyError(f"unknown task_id {task_id!r}")
    task = tasks[task_id]
    arm = arms["fourbar"]
    problem = build_problem_3r(arm, task)
    generator = goal_generator_3r(arm, task, contract)
    max_cands = max_candidates_3r(task, contract)

    direct = InputLinearDirectPlanner(
        goal_generator=generator,
        max_candidates=max_cands,
    ).solve(problem)
    prm = PRMPlanner(
        seed=seed,
        n_samples=60,
        k_neighbors=8,
        max_edge_u=1.5,
        max_goal_candidates=max_cands,
        goal_generator=generator,
    ).solve(problem)
    rrt = RRTConnectPlanner(
        seed=seed,
        max_iterations=600,
        step_u=0.4,
        goal_bias=0.12,
        max_goal_candidates=max_cands,
        goal_generator=generator,
    ).solve(problem)

    return {
        "task_id": task.task_id,
        "task_family": task.task_family,
        "dof": int(arm.robot.dof),
        "start_q": np.asarray(problem.start.q, dtype=np.float64).tolist(),
        "direct_status": str(direct.status),
        "direct_cost": direct.objective_cost,
        "prm_status": str(prm.status),
        "prm_cost": prm.objective_cost,
        "rrt_status": str(rrt.status),
        "rrt_cost": rrt.objective_cost,
        "all_attempted": True,
        "any_success": any(
            r.status is PlanningStatus.SUCCESS for r in (direct, prm, rrt)
        ),
    }


__all__ = ["run_planar3r_planner_smoke"]
