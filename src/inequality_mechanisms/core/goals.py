"""Version 3 goal predicates and candidate generation (ADR-021, ADR-023)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.state import PhysicalState, StateCandidate

if TYPE_CHECKING:
    from inequality_mechanisms.core.robot import RobotModel


@dataclass(frozen=True, slots=True)
class GoalResidual:
    """Task-space residual of a physical state against a goal predicate."""

    primary: float
    components: NDArray[np.float64] | None = None
    extras: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not np.isfinite(self.primary):
            raise ValueError("primary residual must be finite")
        if self.components is not None:
            object.__setattr__(
                self,
                "components",
                np.asarray(self.components, dtype=np.float64).copy(),
            )
        object.__setattr__(self, "extras", dict(self.extras))


@dataclass(frozen=True, slots=True)
class GoalSamplingRequest:
    """Parameters for generating physical goal candidates from a predicate."""

    max_candidates: int
    seed: int | None = None
    representation_hint: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        object.__setattr__(self, "extras", dict(self.extras))


@runtime_checkable
class GoalConstraint(Protocol):
    """Task predicate independent of IK or planner sampling policy."""

    def satisfied(self, state: PhysicalState) -> bool:
        """Return True when ``state`` meets the goal."""

    def residual(self, state: PhysicalState) -> GoalResidual:
        """Return a structured residual of ``state`` against the goal."""


@runtime_checkable
class GoalStateGenerator(Protocol):
    """Separate service that samples physical states for a goal predicate."""

    def generate(
        self,
        robot: RobotModel,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> Sequence[StateCandidate]:
        """Return physical candidates for ``goal`` under ``request``."""


@dataclass(frozen=True, slots=True)
class ExactOutputGoal:
    """Exact output-configuration goal ``q = q_g`` within a tolerance."""

    q_goal: NDArray[np.float64]
    tolerance: float = 1e-9

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "q_goal", np.asarray(self.q_goal, dtype=np.float64).copy()
        )
        if self.q_goal.ndim != 1 or not np.all(np.isfinite(self.q_goal)):
            raise ValueError("q_goal must be a finite 1-D vector")
        if not np.isfinite(self.tolerance) or self.tolerance < 0.0:
            raise ValueError("tolerance must be finite and nonnegative")

    def satisfied(self, state: PhysicalState) -> bool:
        """Return True when ``||q - q_goal||_2 <= tolerance``."""
        return float(np.linalg.norm(state.q - self.q_goal)) <= self.tolerance

    def residual(self, state: PhysicalState) -> GoalResidual:
        """Return Euclidean residual in output coordinates."""
        delta = state.q - self.q_goal
        return GoalResidual(primary=float(np.linalg.norm(delta)), components=delta)
