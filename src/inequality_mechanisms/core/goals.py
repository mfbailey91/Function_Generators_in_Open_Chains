"""Version 3 goal predicates (ADR-021, ADR-023).

Kinematics-specific goal generators live under ``kinematics.*_goals``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import math
import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.kinematics.planar_3r import angular_distance, wrap_to_pi


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
    """Planar Cartesian disk goal ``||f(q) - x_g||_2 <= r`` (ADR-023)."""

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


@dataclass(frozen=True, slots=True)
class PlanarPoseRegionGoal:
    """Planar SE(2) region goal on tip position and heading (Sprint V3.7)."""

    center: NDArray[np.float64]
    radius: float
    phi_goal: float
    orientation_tol: float
    robot: RobotModel

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "center", np.asarray(self.center, dtype=np.float64).copy()
        )
        if self.center.shape != (2,) or not np.all(np.isfinite(self.center)):
            raise ValueError("center must be a finite vector with shape (2,)")
        if not np.isfinite(self.radius) or self.radius < 0.0:
            raise ValueError("radius must be finite and nonnegative")
        if not np.isfinite(self.phi_goal):
            raise ValueError("phi_goal must be finite")
        if not np.isfinite(self.orientation_tol) or self.orientation_tol < 0.0:
            raise ValueError("orientation_tol must be finite and nonnegative")
        object.__setattr__(self, "phi_goal", wrap_to_pi(float(self.phi_goal)))

    def _pose(
        self, state: PhysicalState
    ) -> tuple[NDArray[np.float64], float]:
        pose = self.robot.forward_kinematics(state)
        tip = np.asarray(pose.position, dtype=np.float64)
        if tip.shape != (2,):
            raise ValueError("PlanarPoseRegionGoal requires planar tip shape (2,)")
        if pose.orientation is None:
            raise ValueError("PlanarPoseRegionGoal requires planar orientation")
        ori = np.asarray(pose.orientation, dtype=np.float64)
        if ori.size < 1 or not np.isfinite(ori[0]):
            raise ValueError("PlanarPoseRegionGoal orientation must be finite")
        return tip, wrap_to_pi(float(ori[0]))

    def satisfied(self, state: PhysicalState) -> bool:
        """Return True when tip and heading lie in the SE(2) region."""
        tip, phi = self._pose(state)
        dist = float(np.linalg.norm(tip - self.center))
        ang = angular_distance(phi, self.phi_goal)
        return dist <= self.radius and ang <= self.orientation_tol

    def residual(self, state: PhysicalState) -> GoalResidual:
        """Return combined SE(2) residual with position/orientation extras."""
        tip, phi = self._pose(state)
        delta = tip - self.center
        dist = float(np.linalg.norm(delta))
        ang = angular_distance(phi, self.phi_goal)
        pos_excess = max(0.0, dist - float(self.radius))
        ori_excess = max(0.0, ang - float(self.orientation_tol))
        primary = float(math.hypot(pos_excess, ori_excess))
        return GoalResidual(
            primary=primary,
            components=np.asarray([dist, ang], dtype=np.float64),
            extras={
                "cartesian_distance": dist,
                "signed_disk_residual": dist - float(self.radius),
                "angular_distance": ang,
                "signed_orientation_residual": ang - float(self.orientation_tol),
                "phi": phi,
                "phi_goal": float(self.phi_goal),
            },
        )
