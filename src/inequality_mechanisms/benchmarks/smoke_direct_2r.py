"""Deterministic free-space direct-planner smoke pack (Sprint V3.2 / V3-204)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.adapters.planar_2r_robot import (
    planar_2r_operating_branch_robot,
)
from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import CartesianDiskGoal
from inequality_mechanisms.kinematics.planar_2r_goals import CartesianDiskGoalGenerator
from inequality_mechanisms.core.local_motion import (
    EndpointDeclaredMotion,
    InputLinearMotion,
    OutputLinearMotion,
)
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult
from inequality_mechanisms.core.scene import FreeSpaceScene
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch
from inequality_mechanisms.planners.direct.input_linear import InputLinearDirectPlanner
from inequality_mechanisms.planners.direct.output_linear import OutputLinearDirectPlanner

MechanismName = Literal["fourbar", "gearbox"]
TaskKind = Literal["already_satisfied", "direct_feasible", "invalid_unrepresentable"]

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


def _fourbar_2d_branch() -> OperatingBranch:
    """Certified 2-D crank-rocker pair matching the V2 graph fixture."""
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


@dataclass(frozen=True, slots=True)
class SmokeTask:
    """One hand-chosen exact-start Cartesian disk task."""

    task_id: str
    kind: TaskKind
    mechanism: MechanismName
    start_u_frac: tuple[float, float]
    goal_center: NDArray[np.float64] | None
    goal_radius: float
    goal_region_descriptor: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SmokeArm:
    """Paired mechanism arm for the smoke pack."""

    name: MechanismName
    branch: OperatingBranch
    robot: Any


def build_paired_arms(*, L1: float = 1.0, L2: float = 1.0) -> dict[MechanismName, SmokeArm]:
    """Return four-bar and span-matched gearbox robots sharing planar FK."""
    fk = Planar2R(L1=L1, L2=L2)
    fourbar = _fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    return {
        "fourbar": SmokeArm(
            name="fourbar",
            branch=fourbar,
            robot=planar_2r_operating_branch_robot(fourbar, planar_fk=fk),
        ),
        "gearbox": SmokeArm(
            name="gearbox",
            branch=gearbox,
            robot=planar_2r_operating_branch_robot(gearbox, planar_fk=fk),
        ),
    }


def _state_from_frac(arm: SmokeArm, frac: tuple[float, float]) -> PhysicalState:
    cert = arm.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    u = u_lo + np.asarray(frac, dtype=np.float64) * (u_hi - u_lo)
    return arm.robot.state_from_input(u)


def smoke_task_catalog(arms: dict[MechanismName, SmokeArm]) -> tuple[SmokeTask, ...]:
    """Hand-chosen deterministic tasks (not a population study)."""
    tasks: list[SmokeTask] = []
    for mech, arm in arms.items():
        start_near = _state_from_frac(arm, (0.20, 0.22))
        tip_near = np.asarray(arm.robot.forward_kinematics(start_near).position)
        goal_state = _state_from_frac(arm, (0.55, 0.58))
        tip_goal = np.asarray(arm.robot.forward_kinematics(goal_state).position)
        tasks.append(
            SmokeTask(
                task_id=f"{mech}_already_satisfied",
                kind="already_satisfied",
                mechanism=mech,
                start_u_frac=(0.20, 0.22),
                goal_center=tip_near.copy(),
                goal_radius=0.08,
                goal_region_descriptor={
                    "type": "cartesian_disk",
                    "center": tip_near.tolist(),
                    "radius": 0.08,
                },
            )
        )
        tasks.append(
            SmokeTask(
                task_id=f"{mech}_direct_feasible",
                kind="direct_feasible",
                mechanism=mech,
                start_u_frac=(0.20, 0.22),
                goal_center=tip_goal.copy(),
                goal_radius=0.05,
                goal_region_descriptor={
                    "type": "cartesian_disk",
                    "center": tip_goal.tolist(),
                    "radius": 0.05,
                },
            )
        )
        tasks.append(
            SmokeTask(
                task_id=f"{mech}_invalid_unrepresentable",
                kind="invalid_unrepresentable",
                mechanism=mech,
                start_u_frac=(0.20, 0.22),
                goal_center=np.asarray([1.8, 0.0], dtype=np.float64),
                goal_radius=0.05,
                goal_region_descriptor={
                    "type": "cartesian_disk",
                    "center": [1.8, 0.0],
                    "radius": 0.05,
                },
            )
        )
    return tuple(tasks)


def build_problem(arm: SmokeArm, task: SmokeTask) -> PlanningProblem:
    """Build an exact-start Cartesian disk planning problem."""
    if task.goal_center is None:
        raise ValueError("smoke task requires a goal center")
    start = _state_from_frac(arm, task.start_u_frac)
    goal = CartesianDiskGoal(
        center=task.goal_center,
        radius=task.goal_radius,
        robot=arm.robot,
    )
    return PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )


def run_smoke_task(
    arm: SmokeArm,
    task: SmokeTask,
    *,
    planner_name: Literal["output_linear", "input_linear"],
) -> PlanningResult:
    """Solve one smoke task with a named direct planner."""
    problem = build_problem(arm, task)
    fk = arm.robot.planar_fk
    assert fk is not None
    generator = CartesianDiskGoalGenerator(planar_fk=fk)
    if planner_name == "output_linear":
        planner = OutputLinearDirectPlanner(goal_generator=generator)
    else:
        planner = InputLinearDirectPlanner(goal_generator=generator)
    result = planner.solve(problem)
    # Attach goal-region descriptor for result inspection (not a schema change).
    metrics = dict(result.planner_metrics)
    direct = dict(metrics.get("direct", {}))
    direct["goal_region_descriptor"] = dict(task.goal_region_descriptor)
    metrics["direct"] = direct
    return PlanningResult(
        status=result.status,
        trajectory=result.trajectory,
        selected_goal_state=result.selected_goal_state,
        total_wall_time_s=result.total_wall_time_s,
        objective_cost=result.objective_cost,
        path_length_u=result.path_length_u,
        path_length_q=result.path_length_q,
        path_length_x=result.path_length_x,
        task_class=result.task_class,
        final_goal_residual=result.final_goal_residual,
        planner_metrics=metrics,
        provenance=result.provenance,
        setup_time_s=result.setup_time_s,
        preprocessing_time_s=result.preprocessing_time_s,
        query_time_s=result.query_time_s,
        postprocessing_time_s=result.postprocessing_time_s,
        state_validity_checks=result.state_validity_checks,
        motion_validity_checks=result.motion_validity_checks,
        collision_checks=result.collision_checks,
    )


def run_smoke_pack() -> list[dict[str, Any]]:
    """Run the deterministic paired smoke pack; return summary rows."""
    arms = build_paired_arms()
    rows: list[dict[str, Any]] = []
    for task in smoke_task_catalog(arms):
        arm = arms[task.mechanism]
        for planner_name in ("output_linear", "input_linear"):
            result = run_smoke_task(arm, task, planner_name=planner_name)
            rows.append(
                {
                    "task_id": task.task_id,
                    "kind": task.kind,
                    "mechanism": task.mechanism,
                    "planner": planner_name,
                    "status": str(result.status),
                    "task_class": result.task_class,
                    "objective_cost": result.objective_cost,
                    "architecture_version": result.provenance.architecture_version,
                }
            )
    return rows


# Re-export connector types for tests that build problems manually.
__all__ = [
    "InputLinearMotion",
    "OutputLinearMotion",
    "SmokeArm",
    "SmokeTask",
    "build_paired_arms",
    "build_problem",
    "run_smoke_pack",
    "run_smoke_task",
    "smoke_task_catalog",
]
