"""Version 3 planning results (ADR-021, ADR-026)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from inequality_mechanisms.core.goal_residuals import GoalResidualReport
from inequality_mechanisms.core.goals import GoalResidual
from inequality_mechanisms.core.state import PhysicalState, StateCandidate


class PlanningStatus(StrEnum):
    """Post-search planner outcome (distinct from pre-search task class)."""

    SUCCESS = "success"
    UNSOLVED = "unsolved"
    TIMEOUT = "timeout"
    INVALID = "invalid"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Trajectory:
    """Ordered physical states along a planned path."""

    states: tuple[PhysicalState, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "states", tuple(self.states))


@dataclass(frozen=True, slots=True)
class ResultProvenance:
    """Reproducibility metadata for a planning result."""

    architecture_version: int
    code_revision: str | None = None
    planner_id: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "extras", dict(self.extras))


@dataclass(frozen=True, slots=True)
class PlanningResult:
    """Common planning result schema across planner families."""

    status: PlanningStatus
    trajectory: Trajectory | None
    selected_goal_state: PhysicalState | None
    total_wall_time_s: float
    objective_cost: float | None
    path_length_u: float | None
    path_length_q: float | None
    path_length_x: float | None
    task_class: str | None
    final_goal_residual: GoalResidual | None
    planner_metrics: Mapping[str, Any]
    provenance: ResultProvenance
    setup_time_s: float | None = None
    preprocessing_time_s: float | None = None
    query_time_s: float | None = None
    postprocessing_time_s: float | None = None
    state_validity_checks: int | None = None
    motion_validity_checks: int | None = None
    collision_checks: int | None = None
    selected_goal_candidate: StateCandidate | None = None
    goal_residuals: GoalResidualReport | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "planner_metrics", dict(self.planner_metrics))
        if (
            self.selected_goal_candidate is not None
            and self.selected_goal_state is not None
        ):
            cand_state = self.selected_goal_candidate.state
            if not (
                np.allclose(cand_state.u, self.selected_goal_state.u)
                and np.allclose(cand_state.q, self.selected_goal_state.q)
            ):
                raise ValueError(
                    "selected_goal_candidate.state must match selected_goal_state"
                )
