"""Version 3 planner-independent core types (Sprint V3.1 / ADR-021–025)."""

from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import (
    ExactOutputGoal,
    GoalConstraint,
    GoalResidual,
    GoalSamplingRequest,
    GoalStateGenerator,
)
from inequality_mechanisms.core.local_motion import (
    EndpointDeclaredMotion,
    LocalMotion,
    LocalMotionModel,
)
from inequality_mechanisms.core.objectives import (
    ActuatorTravelObjective,
    Cost,
    IncrementalPlanningObjective,
    PlanningObjective,
)
from inequality_mechanisms.core.planner import (
    Planner,
    PlannerCapabilities,
    PlannerLifecycle,
)
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.scene import FreeSpaceScene, PlanningScene
from inequality_mechanisms.core.serialize import (
    physical_state_from_dict,
    physical_state_to_dict,
    planner_capabilities_from_dict,
    planner_capabilities_to_dict,
    planning_result_from_dict,
    planning_result_to_dict,
)
from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate

__all__ = [
    "ActuatorTravelObjective",
    "ConstraintSet",
    "Cost",
    "EndpointDeclaredMotion",
    "ExactOutputGoal",
    "FreeSpaceScene",
    "GoalConstraint",
    "GoalResidual",
    "GoalSamplingRequest",
    "GoalStateGenerator",
    "IncrementalPlanningObjective",
    "LocalMotion",
    "LocalMotionModel",
    "PhysicalState",
    "Planner",
    "PlannerCapabilities",
    "PlannerLifecycle",
    "PlanningObjective",
    "PlanningProblem",
    "PlanningResult",
    "PlanningScene",
    "PlanningStatus",
    "Pose",
    "ResultProvenance",
    "RobotModel",
    "StateCandidate",
    "Trajectory",
    "physical_state_from_dict",
    "physical_state_to_dict",
    "planner_capabilities_from_dict",
    "planner_capabilities_to_dict",
    "planning_result_from_dict",
    "planning_result_to_dict",
]
