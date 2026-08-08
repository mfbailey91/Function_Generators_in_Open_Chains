"""Deterministic free-space PRM / RRT-Connect smoke pack (Sprint V3.4 / V3-404)."""

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
from inequality_mechanisms.core.local_motion import InputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult, PlanningStatus
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
from inequality_mechanisms.planners.roadmap import PRMPlanner
from inequality_mechanisms.planners.tree import RRTConnectPlanner

MechanismName = Literal["fourbar", "gearbox"]
PlannerName = Literal["prm", "rrt_connect"]

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)
SMOKE_SEED = 7


def _fourbar_2d_branch() -> OperatingBranch:
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


@dataclass(frozen=True, slots=True)
class SamplingSmokeArm:
    """Paired mechanism arm for sampling-planner smoke."""

    name: MechanismName
    branch: OperatingBranch
    robot: Any


@dataclass(frozen=True, slots=True)
class SamplingSmokeTask:
    """One hand-chosen exact-start Cartesian disk task."""

    task_id: str
    mechanism: MechanismName
    start_u_frac: tuple[float, float]
    goal_center: NDArray[np.float64]
    goal_radius: float
    kind: Literal["already_satisfied", "planning_feasible"]


def build_paired_arms(*, L1: float = 1.0, L2: float = 1.0) -> dict[MechanismName, SamplingSmokeArm]:
    """Return four-bar and span-matched gearbox robots sharing planar FK."""
    fk = Planar2R(L1=L1, L2=L2)
    fourbar = _fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    return {
        "fourbar": SamplingSmokeArm(
            name="fourbar",
            branch=fourbar,
            robot=planar_2r_operating_branch_robot(fourbar, planar_fk=fk),
        ),
        "gearbox": SamplingSmokeArm(
            name="gearbox",
            branch=gearbox,
            robot=planar_2r_operating_branch_robot(gearbox, planar_fk=fk),
        ),
    }


def _state_from_frac(arm: SamplingSmokeArm, frac: tuple[float, float]) -> PhysicalState:
    cert = arm.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    u = u_lo + np.asarray(frac, dtype=np.float64) * (u_hi - u_lo)
    return arm.robot.state_from_input(u)


def smoke_task_catalog(
    arms: dict[MechanismName, SamplingSmokeArm],
) -> tuple[SamplingSmokeTask, ...]:
    """Hand-chosen tasks (not a population study)."""
    tasks: list[SamplingSmokeTask] = []
    for mech, arm in arms.items():
        start = _state_from_frac(arm, (0.25, 0.28))
        tip_start = np.asarray(arm.robot.forward_kinematics(start).position)
        goal_state = _state_from_frac(arm, (0.70, 0.72))
        tip_goal = np.asarray(arm.robot.forward_kinematics(goal_state).position)
        tasks.append(
            SamplingSmokeTask(
                task_id=f"{mech}_already_satisfied",
                mechanism=mech,
                start_u_frac=(0.25, 0.28),
                goal_center=tip_start.copy(),
                goal_radius=0.08,
                kind="already_satisfied",
            )
        )
        tasks.append(
            SamplingSmokeTask(
                task_id=f"{mech}_planning_feasible",
                mechanism=mech,
                start_u_frac=(0.25, 0.28),
                goal_center=tip_goal.copy(),
                goal_radius=0.06,
                kind="planning_feasible",
            )
        )
    return tuple(tasks)


def build_problem(arm: SamplingSmokeArm, task: SamplingSmokeTask) -> PlanningProblem:
    """Build an exact-start Cartesian disk planning problem."""
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
        local_motion=InputLinearMotion(robot=arm.robot, n_samples=12),
        objective=ActuatorTravelObjective(),
    )


def run_smoke_task(
    arm: SamplingSmokeArm,
    task: SamplingSmokeTask,
    *,
    planner_name: PlannerName,
    seed: int = SMOKE_SEED,
) -> PlanningResult:
    """Solve one smoke task with PRM or RRT-Connect."""
    problem = build_problem(arm, task)
    fk = arm.robot.planar_fk
    assert fk is not None
    generator = CartesianDiskGoalGenerator(planar_fk=fk)
    if planner_name == "prm":
        planner = PRMPlanner(
            seed=seed,
            n_samples=80,
            k_neighbors=10,
            max_edge_u=1.25,
            goal_generator=generator,
        )
    else:
        planner = RRTConnectPlanner(
            seed=seed,
            max_iterations=800,
            step_u=0.35,
            goal_bias=0.1,
            goal_generator=generator,
        )
    return planner.solve(problem)


def run_sampling_smoke_pack(*, seed: int = SMOKE_SEED) -> list[dict[str, Any]]:
    """Run the paired sampling smoke pack; return summary rows."""
    arms = build_paired_arms()
    rows: list[dict[str, Any]] = []
    for task in smoke_task_catalog(arms):
        arm = arms[task.mechanism]
        for planner_name in ("prm", "rrt_connect"):
            result = run_smoke_task(
                arm, task, planner_name=planner_name, seed=seed
            )
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
                    "seed": result.provenance.extras.get("seed"),
                }
            )
    return rows


__all__ = [
    "SMOKE_SEED",
    "SamplingSmokeArm",
    "SamplingSmokeTask",
    "build_paired_arms",
    "build_problem",
    "run_sampling_smoke_pack",
    "run_smoke_task",
    "smoke_task_catalog",
]
