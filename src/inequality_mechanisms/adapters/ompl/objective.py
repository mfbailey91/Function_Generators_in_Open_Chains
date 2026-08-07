"""Path-cost helpers for OMPL adapter postprocessing (V3-503)."""

from __future__ import annotations

from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_space import path_cost_u, path_length_q

__all__ = ["path_cost_u", "path_length_q", "objective_cost_from_states"]


def objective_cost_from_states(states: tuple[PhysicalState, ...]) -> float:
    """Actuator-travel cost along an extracted OMPL path polyline in ``U``."""
    return path_cost_u(states)
