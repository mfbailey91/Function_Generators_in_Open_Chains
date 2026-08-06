"""Version 3 planning problem container (ADR-021)."""

from __future__ import annotations

from dataclasses import dataclass

from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import GoalConstraint
from inequality_mechanisms.core.local_motion import LocalMotionModel
from inequality_mechanisms.core.objectives import PlanningObjective
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.scene import PlanningScene
from inequality_mechanisms.core.state import PhysicalState


@dataclass(frozen=True, slots=True)
class PlanningProblem:
    """Planner-independent motion-planning problem."""

    robot: RobotModel
    scene: PlanningScene
    start: PhysicalState
    goal: GoalConstraint
    path_constraints: ConstraintSet
    local_motion: LocalMotionModel
    objective: PlanningObjective
