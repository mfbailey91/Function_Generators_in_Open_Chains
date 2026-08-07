"""Bounded OMPL vs native PRM/RRTConnect parity smoke (Sprint V3.5 / V3-504)."""

from __future__ import annotations

from typing import Any, Literal

from inequality_mechanisms.adapters.ompl import is_ompl_available
from inequality_mechanisms.adapters.ompl.prm import OmplPRMPlanner
from inequality_mechanisms.adapters.ompl.rrt_connect import OmplRRTConnectPlanner
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    SamplingSmokeArm,
    SamplingSmokeTask,
    build_paired_arms,
    build_problem,
    run_smoke_task,
    smoke_task_catalog,
)
from inequality_mechanisms.core.goals import CartesianDiskGoalGenerator
from inequality_mechanisms.core.results import PlanningResult, PlanningStatus

OmplPlannerName = Literal["ompl_prm", "ompl_rrt_connect"]
NativePlannerName = Literal["prm", "rrt_connect"]

_OMPL_TO_NATIVE: dict[OmplPlannerName, NativePlannerName] = {
    "ompl_prm": "prm",
    "ompl_rrt_connect": "rrt_connect",
}


def run_ompl_smoke_task(
    arm: SamplingSmokeArm,
    task: SamplingSmokeTask,
    *,
    planner_name: OmplPlannerName,
    seed: int = SMOKE_SEED,
    solve_time_s: float = 2.0,
) -> PlanningResult:
    """Solve one smoke task with an OMPL adapter planner."""
    if not is_ompl_available():
        raise ImportError("OMPL bindings are required for run_ompl_smoke_task")
    problem = build_problem(arm, task)
    fk = arm.robot.planar_fk
    assert fk is not None
    generator = CartesianDiskGoalGenerator(planar_fk=fk)
    if planner_name == "ompl_prm":
        planner = OmplPRMPlanner(
            seed=seed,
            goal_generator=generator,
            solve_time_s=solve_time_s,
            max_nearest_neighbors=10,
        )
    else:
        planner = OmplRRTConnectPlanner(
            seed=seed,
            goal_generator=generator,
            solve_time_s=solve_time_s,
            range_u=0.35,
        )
    return planner.solve(problem)


def run_ompl_parity_smoke_pack(
    *,
    seed: int = SMOKE_SEED,
    solve_time_s: float = 2.0,
) -> list[dict[str, Any]]:
    """Run OMPL + native on shared smoke tasks; return paired summary rows."""
    if not is_ompl_available():
        raise ImportError("OMPL bindings are required for run_ompl_parity_smoke_pack")
    arms = build_paired_arms()
    rows: list[dict[str, Any]] = []
    for task in smoke_task_catalog(arms):
        arm = arms[task.mechanism]
        for ompl_name, native_name in _OMPL_TO_NATIVE.items():
            ompl_result = run_ompl_smoke_task(
                arm,
                task,
                planner_name=ompl_name,
                seed=seed,
                solve_time_s=solve_time_s,
            )
            native_result = run_smoke_task(
                arm, task, planner_name=native_name, seed=seed
            )
            rows.append(
                {
                    "task_id": task.task_id,
                    "kind": task.kind,
                    "mechanism": task.mechanism,
                    "ompl_planner": ompl_name,
                    "native_planner": native_name,
                    "ompl_status": str(ompl_result.status),
                    "native_status": str(native_result.status),
                    "ompl_task_class": ompl_result.task_class,
                    "native_task_class": native_result.task_class,
                    "ompl_objective_cost": ompl_result.objective_cost,
                    "native_objective_cost": native_result.objective_cost,
                    "ompl_provenance_planner_id": ompl_result.provenance.planner_id,
                    "native_provenance_planner_id": native_result.provenance.planner_id,
                    "same_task_class": ompl_result.task_class == native_result.task_class,
                    "both_success_when_native_success": (
                        native_result.status != PlanningStatus.SUCCESS
                        or ompl_result.status == PlanningStatus.SUCCESS
                    ),
                }
            )
    return rows


__all__ = [
    "run_ompl_parity_smoke_pack",
    "run_ompl_smoke_task",
]
