"""Version 3 planning scene protocols (ADR-021)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

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
    n_motion_samples :
        Number of samples used when validating continuous local motions
        (endpoints inclusive). Interior samples check joint/mechanism limits
        along connector sample arrays when present.
    """

    robot: RobotModel
    state_tolerance: float = 1e-8
    n_motion_samples: int = 9

    def __post_init__(self) -> None:
        if self.n_motion_samples < 2:
            raise ValueError("n_motion_samples must be >= 2")

    def state_is_valid(self, state: PhysicalState) -> bool:
        """Validate consistency and joint/mechanism limits."""
        if not self.robot.validate_state(state, self.state_tolerance):
            return False
        return self.robot.state_within_limits(state)

    def motion_is_valid(self, motion: LocalMotion) -> bool:
        """Validate endpoints and sampled midpoints along the local motion."""
        if not self.state_is_valid(motion.start) or not self.state_is_valid(motion.end):
            return False
        sample_u = motion.parameters.get("sample_u")
        sample_q = motion.parameters.get("sample_q")
        if sample_u is None or sample_q is None:
            return True
        u_arr = np.asarray(sample_u, dtype=np.float64)
        q_arr = np.asarray(sample_q, dtype=np.float64)
        if u_arr.ndim != 2 or q_arr.ndim != 2 or u_arr.shape[0] != q_arr.shape[0]:
            return False
        n = u_arr.shape[0]
        if n < 2:
            return False
        indices = np.unique(
            np.linspace(0, n - 1, num=min(self.n_motion_samples, n), dtype=int)
        )
        assembly = motion.start.assembly_state
        for idx in indices:
            sample = PhysicalState(
                u=u_arr[idx],
                q=q_arr[idx],
                assembly_state=assembly,
            )
            if not self.state_is_valid(sample):
                return False
        return True
