"""OMPL objective bridge for the V3.5 actuator-space special case (V3-503)."""

from __future__ import annotations

from typing import Any

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.core.local_motion import InputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_space import path_cost_u, path_length_q

__all__ = [
    "build_ompl_objective",
    "path_cost_u",
    "path_length_q",
    "objective_cost_from_states",
]


def build_ompl_objective(
    si: Any, problem: PlanningProblem
) -> tuple[Any, dict[str, str]]:
    """Map actuator travel to OMPL path length only when the equivalence is exact."""
    if not isinstance(problem.objective, ActuatorTravelObjective):
        raise ValueError("OMPL V3.5 objective bridge requires ActuatorTravelObjective")
    if not isinstance(problem.local_motion, InputLinearMotion):
        raise ValueError("OMPL V3.5 objective bridge requires InputLinearMotion")
    ob, _og = require_ompl()
    objective = ob.PathLengthOptimizationObjective(si)
    return objective, {
        "objective_adapter": "actuator_travel_to_ompl_path_length",
        "objective_equivalence": "exact_for_input_linear_euclidean_u",
        "ompl_motion_cost": "euclidean_u",
    }


def objective_cost_from_states(states: tuple[PhysicalState, ...]) -> float:
    """Actuator-travel cost along an extracted OMPL path polyline in ``U``."""
    return path_cost_u(states)
