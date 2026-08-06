"""Version 3 goal predicates and candidate generation (ADR-021, ADR-023)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.kinematics.planar_2r import Planar2R


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


@dataclass(frozen=True, slots=True)
class CartesianDiskGoal:
    """Planar Cartesian disk goal ``||f(q) - x_g||_2 <= r`` (ADR-023).

    Parameters
    ----------
    center :
        Disk center in Cartesian coordinates, shape ``(2,)``.
    radius :
        Nonnegative disk radius.
    robot :
        Robot providing ``forward_kinematics`` for tip position.
    """

    center: NDArray[np.float64]
    radius: float
    robot: RobotModel

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "center", np.asarray(self.center, dtype=np.float64).copy()
        )
        if self.center.shape != (2,) or not np.all(np.isfinite(self.center)):
            raise ValueError("center must be a finite vector with shape (2,)")
        if not np.isfinite(self.radius) or self.radius < 0.0:
            raise ValueError("radius must be finite and nonnegative")

    def _tip(self, state: PhysicalState) -> NDArray[np.float64]:
        pose = self.robot.forward_kinematics(state)
        tip = np.asarray(pose.position, dtype=np.float64)
        if tip.shape != (2,):
            raise ValueError("CartesianDiskGoal requires planar tip shape (2,)")
        return tip

    def satisfied(self, state: PhysicalState) -> bool:
        """Return True when the tip lies inside or on the disk."""
        dist = float(np.linalg.norm(self._tip(state) - self.center))
        return dist <= self.radius

    def residual(self, state: PhysicalState) -> GoalResidual:
        """Return Cartesian distance; extras include signed disk residual."""
        tip = self._tip(state)
        delta = tip - self.center
        dist = float(np.linalg.norm(delta))
        return GoalResidual(
            primary=dist,
            components=delta,
            extras={
                "cartesian_distance": dist,
                "signed_disk_residual": dist - float(self.radius),
            },
        )


def planar_2r_ik_family(q: ArrayLike, *, tolerance: float = 1e-9) -> str:
    """Return ``elbow_up`` / ``elbow_down`` / ``singular`` for planar 2R ``q``."""
    q_arr = np.asarray(q, dtype=np.float64)
    if q_arr.shape != (2,):
        raise ValueError("q must have shape (2,)")
    s = float(np.sin(q_arr[1]))
    if abs(s) <= tolerance:
        return "singular"
    return "elbow_up" if s > 0.0 else "elbow_down"


@dataclass(frozen=True, slots=True)
class CartesianDiskGoalGenerator:
    """Generate physical candidates at the disk center via planar 2R IK.

    Candidates are filtered through ``robot.states_from_output`` and
    ``robot.state_within_limits``. Optional boundary sampling is deferred.
    """

    planar_fk: Planar2R
    limit_tolerance: float = 1e-9

    def generate(
        self,
        robot: RobotModel,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> Sequence[StateCandidate]:
        """Return representable IK lifts of the disk center."""
        if not isinstance(goal, CartesianDiskGoal):
            raise TypeError(
                "CartesianDiskGoalGenerator requires CartesianDiskGoal, "
                f"got {type(goal).__name__}"
            )
        qs = self.planar_fk.inverse(goal.center)
        out: list[StateCandidate] = []
        for q in qs:
            q_arr = np.asarray(q, dtype=np.float64)
            family = planar_2r_ik_family(q_arr)
            for cand in robot.states_from_output(q_arr):
                if not robot.state_within_limits(cand.state):
                    continue
                tip = np.asarray(
                    robot.forward_kinematics(cand.state).position, dtype=np.float64
                )
                cart_res = float(np.linalg.norm(tip - goal.center))
                provenance = {
                    **dict(cand.provenance),
                    "ik_family": family,
                    "goal_region": "cartesian_disk_center",
                }
                out.append(
                    StateCandidate(
                        state=cand.state,
                        residual=max(float(cand.residual), cart_res),
                        provenance=provenance,
                    )
                )
                if len(out) >= request.max_candidates:
                    return tuple(out)
        return tuple(out)
