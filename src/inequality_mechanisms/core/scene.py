"""Version 3 planning scene protocols (ADR-021)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from inequality_mechanisms.core.local_motion import LocalMotion
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState


@runtime_checkable
class PlanningScene(Protocol):
    """Validity checks for states and continuous local motions."""

    def state_is_valid(self, state: PhysicalState) -> bool:
        """Return True when ``state`` is valid in this scene."""

    def motion_is_valid(self, motion: LocalMotion) -> bool:
        """Return True when ``motion`` is collision-/limit-valid."""


@dataclass(frozen=True, slots=True)
class FreeSpaceScene:
    """Free-space scene with mechanism and joint limits only.

    Parameters
    ----------
    robot :
        Robot used for limit and consistency checks.
    state_tolerance :
        Consistency tolerance passed to ``robot.validate_state``.
    """

    robot: RobotModel
    state_tolerance: float = 1e-8

    def state_is_valid(self, state: PhysicalState) -> bool:
        """Validate consistency and joint/mechanism limits."""
        if not self.robot.validate_state(state, self.state_tolerance):
            return False
        return self.robot.state_within_limits(state)

    def motion_is_valid(self, motion: LocalMotion) -> bool:
        """Validate endpoints; continuous clearance is deferred to later sprints."""
        return self.state_is_valid(motion.start) and self.state_is_valid(motion.end)
