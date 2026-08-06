"""Version 3 planning objectives (ADR-021, ADR-024)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from inequality_mechanisms.core.goals import GoalConstraint
from inequality_mechanisms.core.local_motion import LocalMotion
from inequality_mechanisms.core.state import PhysicalState

#: Ordered scalar cost for the initial actuator-path studies.
Cost = float


@runtime_checkable
class PlanningObjective(Protocol):
    """Objective evaluated on complete trajectories."""

    @property
    def objective_id(self) -> str:
        """Stable registry name for this objective."""

    def trajectory_cost(self, states: tuple[PhysicalState, ...]) -> Cost:
        """Return the cost of a piecewise path through ``states``."""


@runtime_checkable
class IncrementalPlanningObjective(PlanningObjective, Protocol):
    """Objective algebra required by informed / incremental planners."""

    def identity_cost(self) -> Cost:
        """Return the zero / identity cost element."""

    def motion_cost(self, motion: LocalMotion) -> Cost:
        """Return the cost of one local motion."""

    def combine(self, prefix: Cost, edge: Cost) -> Cost:
        """Combine a path prefix cost with an edge cost."""

    def is_better(self, a: Cost, b: Cost) -> bool:
        """Return True when ``a`` is strictly better than ``b``."""

    def cost_to_go_lower_bound(
        self,
        state: PhysicalState,
        goal: GoalConstraint,
    ) -> Cost:
        """Return an admissible cost-to-go lower bound at ``state``."""


@dataclass(frozen=True, slots=True)
class ActuatorTravelObjective:
    """Actuator-path length objective (ADR-024).

    Prefer ``LocalMotion.parameters["actuator_path_length"]`` when a connector
    records an analytic or numerically integrated cost. Otherwise fall back to
    endpoint Euclidean displacement ``||u_end - u_start||_2``, which is exact
    for input-linear motion and matches Version 2 discrete edge semantics.
    """

    objective_id: str = "actuator_travel"

    def identity_cost(self) -> Cost:
        """Return zero."""
        return 0.0

    def motion_cost(self, motion: LocalMotion) -> Cost:
        """Return integrated/declared actuator length or endpoint fallback."""
        declared = motion.parameters.get("actuator_path_length")
        if declared is not None:
            return float(declared)
        return float(np.linalg.norm(motion.end.u - motion.start.u))

    def combine(self, prefix: Cost, edge: Cost) -> Cost:
        """Return ``prefix + edge``."""
        return float(prefix + edge)

    def is_better(self, a: Cost, b: Cost) -> bool:
        """Return True when ``a < b``."""
        return a < b

    def trajectory_cost(self, states: tuple[PhysicalState, ...]) -> Cost:
        """Sum endpoint actuator displacements along ``states``."""
        if len(states) < 2:
            return 0.0
        total = 0.0
        for a, b in zip(states[:-1], states[1:]):
            total += float(np.linalg.norm(b.u - a.u))
        return total

    def cost_to_go_lower_bound(
        self,
        state: PhysicalState,
        goal: GoalConstraint,
    ) -> Cost:
        """Lower-bound using exact-output goals when available; else zero."""
        from inequality_mechanisms.core.goals import ExactOutputGoal

        if isinstance(goal, ExactOutputGoal):
            # Without a unique inverse at the goal q, fall back to zero.
            # Graph adapters supply the V2 admissible heuristic instead.
            return 0.0
        return 0.0
