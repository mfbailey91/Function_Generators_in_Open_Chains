"""Version 3 planner-independent core types (Sprint V3.1–V3.2 / ADR-021–026)."""

from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goal_residuals import (
    GoalResidualReport,
    build_goal_residual_report,
)
from inequality_mechanisms.core.goals import (
    CartesianDiskGoal,
    ExactOutputGoal,
    GoalConstraint,
    GoalResidual,
    GoalSamplingRequest,
    GoalStateGenerator,
    PlanarPoseRegionGoal,
)
from inequality_mechanisms.core.local_motion import (
    EndpointDeclaredMotion,
    InputLinearMotion,
    LocalMotion,
    LocalMotionModel,
    OutputLinearMotion,
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
from inequality_mechanisms.kinematics.planar_2r_goals import (
    CartesianDiskGoalGenerator,
    planar_2r_ik_family,
)
from inequality_mechanisms.kinematics.planar_3r_goals import (
    FrozenPlanar3RPositionGoalGenerator,
    Planar3RPoseGoalGenerator,
)

__all__ = [
    "ActuatorTravelObjective",
    "CartesianDiskGoal",
    "CartesianDiskGoalGenerator",
    "ConstraintSet",
    "Cost",
    "EndpointDeclaredMotion",
    "ExactOutputGoal",
    "FreeSpaceScene",
    "FrozenPlanar3RPositionGoalGenerator",
    "GoalConstraint",
    "GoalResidual",
    "GoalResidualReport",
    "GoalSamplingRequest",
    "GoalStateGenerator",
    "build_goal_residual_report",
    "IncrementalPlanningObjective",
    "InputLinearMotion",
    "LocalMotion",
    "LocalMotionModel",
    "OutputLinearMotion",
    "PhysicalState",
    "Planar3RPoseGoalGenerator",
    "PlanarPoseRegionGoal",
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
    "planar_2r_ik_family",
    "planner_capabilities_from_dict",
    "planner_capabilities_to_dict",
    "planning_result_from_dict",
    "planning_result_to_dict",
]
